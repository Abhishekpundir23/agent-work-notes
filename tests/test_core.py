import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SOURCE))
try:
    import notes_core as core
except ModuleNotFoundError:
    core = None


class CoreBehavior(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(core, 'The work-record engine has not been implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = core.Store(self.root, 'codex', 'retry')
        self.store.initialize('Fix retry behavior')

    def add(self, ident, text, **kw):
        event = dict(id=ident, kind='decision', text=text, actor='agent', status='asserted')
        event.update(kw)
        return self.store.append(event)

    def test_retry_is_idempotent_but_changed_facts_are_not_discarded(self):
        first = self.add('e1', 'Outcome changed', metadata={'facts': 'failed', 'captured_at': 't1'})
        again = self.add('e1', 'Outcome changed', metadata={'facts': 'failed', 'captured_at': 't2'})
        self.assertEqual(first['seq'], again['seq'])
        with self.assertRaises(ValueError):
            self.add('e1', 'Outcome changed', metadata={'facts': 'passed'})
        self.add('e2', 'Outcome changed', metadata={'facts': 'passed'})
        self.assertEqual(len(self.store.events()), 3)

    def test_transitive_correction_recall_returns_current_fact(self):
        self.add('a', 'Use Jest')
        self.add('b', 'Use Mocha', supersedes=['a'])
        self.add('c', 'Use Vitest', supersedes=['b'])
        self.assertEqual([e['id'] for e in self.store.recall('Jest')], ['c'])
        brief = self.store.brief()
        self.assertIn('Use Vitest', brief)
        self.assertNotIn('Use Jest', brief)
        self.assertEqual(self.store.get('a')['text'], 'Use Jest')

    def test_conflicting_corrections_remain_visible_until_reconciled(self):
        self.add('a', 'Use Jest')
        self.add('b', 'Use Mocha', supersedes=['a'])
        self.add('c', 'Use Vitest', supersedes=['a'])
        self.assertTrue(self.store.state()['conflicts'])
        self.assertIn('CONFLICT', self.store.brief())
        self.add('d', 'User selected Vitest', supersedes=['b', 'c'], actor='user')
        self.assertEqual(self.store.state()['conflicts'], [])

    def test_lower_authority_cannot_replace_user_constraint(self):
        self.add('api', 'Keep public API', kind='constraint', actor='user')
        with self.assertRaises(ValueError):
            self.add('override', 'Change public API', kind='constraint', supersedes=['api'])
        self.assertIn('Keep public API', self.store.brief())

    def test_corrections_invalidate_dependent_guidance_transitively(self):
        self.add('a', 'Use Jest')
        self.add('n', 'Run Jest next', kind='next', depends_on=['a'])
        self.add('n2', 'Report Jest result', kind='next', depends_on=['n'])
        self.add('b', 'Use Vitest', supersedes=['a'])
        self.assertEqual(set(self.store.state()['stale']), {'n', 'n2'})
        self.assertIn('STALE', self.store.brief())
        self.assertNotIn('Run Jest next', self.store.brief())

    def test_atomic_batch_rolls_back_on_invalid_reference(self):
        with self.assertRaises(ValueError):
            self.store.append_many([
                dict(id='a', kind='decision', text='first'),
                dict(id='b', kind='decision', text='second', supersedes=['missing']),
            ])
        self.assertEqual(len(self.store.events()), 1)

    def test_constraints_overflow_has_retrieval_route_and_whole_byte_bound(self):
        for i in range(25):
            self.add(f'c{i}', 'Keep ' + ('अभ्यास ' * 70), kind='constraint', actor='user')
        brief = self.store.brief(max_bytes=1100)
        self.assertLessEqual(len(brief.encode('utf-8')), 1100)
        self.assertIn('OVERFLOW', brief)
        self.assertIn('pending', brief)
        self.assertIn('get', brief)
        self.assertEqual(len(self.store.state()['active']), 26)

    def test_impossibly_small_budget_is_an_error_not_silent_loss(self):
        with self.assertRaises(ValueError):
            self.store.brief(max_bytes=80)

    def test_exact_paths_and_changed_evidence(self):
        (self.root / 'real').mkdir()
        file = self.root / 'real/core.py'
        file.write_text('before')
        digest = core.hash_file(file)
        self.add('a', 'Inspected files', kind='action', evidence=[
            {'path': 'nonexistent/core.py'}, {'path': 'real/core.py', 'sha256': digest}])
        items = self.store.doctor()['evidence']
        self.assertEqual({x['path']: x['state'] for x in items},
                         {'nonexistent/core.py': 'missing', 'real/core.py': 'unchanged'})
        file.write_text('after')
        self.assertEqual(self.store.doctor()['evidence'][1]['state'], 'changed')

    def test_evidence_cannot_escape_project(self):
        with self.assertRaises(ValueError):
            self.add('a', 'Bad reference', evidence=[{'path': '../private'}])
        with tempfile.TemporaryDirectory() as outside:
            (self.root / 'link').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.add('b', 'Symlink escape', evidence=[{'path': 'link/private'}])

    def test_running_failed_reverted_are_distinct_and_history_retained(self):
        self.add('r', 'Test still running', kind='check', status='running')
        self.add('f', 'Tests did not pass', kind='check', status='failed', supersedes=['r'])
        self.add('e', 'Reverted attempt', kind='action', status='reverted')
        state = {e['id']: e['status'] for e in self.store.state()['active']}
        self.assertEqual(state['f'], 'failed')
        self.assertEqual(state['e'], 'reverted')
        self.assertEqual(self.store.get('r')['status'], 'running')

    def test_capture_error_remains_visible(self):
        self.add('gap', 'Git capture failed: permission denied', kind='coverage', status='failed')
        self.assertIn('coverage=partial', self.store.brief())
        self.assertIn('permission denied', self.store.brief())

    def test_task_and_host_are_isolated(self):
        other = core.Store(self.root, 'codex', 'other')
        other.initialize('Different task')
        other.append(dict(id='foreign', kind='constraint', text='Unrelated'))
        self.assertEqual(self.store.recall('Unrelated'), [])
        claude = core.Store(self.root, 'claude', 'retry')
        claude.initialize('Claude only')
        self.assertEqual(len(claude.events()), 1)

    def test_concurrent_writers_keep_distinct_records_and_valid_chain(self):
        def write(i):
            s = core.Store(self.root, 'codex', 'retry')
            return s.append(dict(id=f'w{i}', kind='action', text=f'Action {i}'))
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(write, range(16)))
        self.assertEqual(len(self.store.events()), 17)
        self.assertEqual(self.store.doctor()['ledger_errors'], [])

    def test_projection_consistency_staleness_and_safe_markdown(self):
        self.add('a', '<script>alert(1)</script>\n# malicious heading', kind='note')
        paths = self.store.render(max_bytes=1800)
        manifest = json.loads(Path(paths['manifest']).read_text())
        self.assertEqual(manifest['revision'], self.store.state()['revision'])
        text = Path(paths['map']).read_text()
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)
        self.assertFalse(self.store.doctor()['view_stale'])
        self.add('b', 'New work', kind='action')
        self.assertTrue(self.store.doctor()['view_stale'])
        self.assertEqual(json.loads(Path(paths['manifest']).read_text()), manifest)

    def test_sql_layer_rejects_update_and_delete(self):
        with sqlite3.connect(self.store.db_path) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE events SET payload='{}'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute('DELETE FROM events')

    def test_render_rejects_modified_existing_view(self):
        paths = self.store.render()
        Path(paths['brief']).write_text('Tampered continuation instructions')
        with self.assertRaises(ValueError):
            self.store.render()
        self.assertTrue(self.store.doctor()['view_errors'])

    def test_linear_corrections_do_not_retain_quadratic_ancestry(self):
        import tracemalloc
        rows = [dict(id=f'c{i}', seq=i+1, kind='decision', supersedes=[f'c{i-1}'] if i else [], depends_on=[])
                for i in range(1500)]
        tracemalloc.start()
        try:
            state = self.store.state(rows)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(len(state['active']), 1)
        self.assertEqual(state['conflicts'], [])
        self.assertLess(peak, 12 * 1024 * 1024, 'A linear correction history must use bounded per-event state')

    def test_invalid_scope_and_schema_rejected(self):
        with self.assertRaises(ValueError):
            core.Store(self.root, 'codex', '../other')
        with self.assertRaises(ValueError):
            self.add('a', 'unknown kind', kind='truth')
        with self.assertRaises(ValueError):
            self.add('b', 'invalid status', status='verified')
        with self.assertRaises(ValueError):
            self.add('c', 'huge' * 6000)

    def test_uninitialized_task_does_not_create_false_empty_history(self):
        missing = core.Store(self.root, 'codex', 'missing')
        with self.assertRaises(ValueError):
            missing.brief()


if __name__ == '__main__':
    unittest.main()
