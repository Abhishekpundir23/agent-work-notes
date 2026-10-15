import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class StandaloneCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="notes space ' ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        self.root.mkdir()

    def script(self, host):
        name = ('codex' if host == 'codex' else 'claude') + '-work-notes'
        source = REPO / 'skills' / name
        self.assertTrue((source / 'scripts/notes.py').is_file(), 'Standalone package is not built')
        target = Path(self.tmp.name) / name
        shutil.copytree(source, target, dirs_exist_ok=True)
        return target / 'scripts/notes.py'

    def run_cli(self, script, *args, payload=None, expected=0, task='retry'):
        env = dict(os.environ, PYTHONPATH='')
        result = subprocess.run([sys.executable, str(script), '--root', str(self.root), '--task', task, *args],
                                input=json.dumps(payload) if payload is not None else None,
                                capture_output=True, text=True, cwd=self.root, env=env)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def test_each_folder_is_independently_usable(self):
        for host in ('codex', 'claude'):
            with self.subTest(host=host):
                script = self.script(host)
                self.run_cli(script, 'init', '--objective', 'Fix retry behavior')
                self.run_cli(script, 'add', '--kind', 'constraint', '--actor', 'user', '--text', 'Preserve public API')
                brief = self.run_cli(script, 'brief', '--max-bytes', '900').stdout
                self.assertIn('Preserve public API', brief)
                self.assertLessEqual(len(brief.encode()), 900)
                paths = json.loads(self.run_cli(script, 'render').stdout)
                self.assertTrue(Path(paths['map']).is_file())
                self.assertEqual(json.loads(self.run_cli(script, 'doctor').stdout)['ledger_errors'], [])

    def test_both_hook_paths_preserve_failure_and_replay(self):
        for host in ('codex', 'claude'):
            with self.subTest(host=host):
                script = self.script(host)
                self.run_cli(script, 'init', '--objective', 'Diagnose failure')
                payload = dict(session_id='s', tool_use_id='t', hook_event_name='PostToolUse', tool_name='Bash',
                               tool_input={'command': 'pytest'}, tool_response={'exit_code': 1, 'stdout': 'collected', 'stderr': 'ImportError'})
                if host == 'claude':
                    payload.update(hook_event_name='PostToolUseFailure', error='ImportError', is_interrupt=False)
                self.run_cli(script, 'hook', payload=payload)
                self.run_cli(script, 'hook', payload=payload)
                rows = json.loads(self.run_cli(script, 'recall', '--query', 'ImportError').stdout)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['status'], 'failed')

    def test_lifecycle_stops_do_not_overwrite_and_start_restores_brief(self):
        for host in ('codex', 'claude'):
            with self.subTest(host=host):
                script = self.script(host)
                self.run_cli(script, 'init', '--objective', 'Keep all responses')
                stop = dict(session_id='s', hook_event_name='Stop', last_assistant_message='Still working')
                self.run_cli(script, 'hook', payload=stop)
                self.run_cli(script, 'hook', payload=stop)
                rows = json.loads(self.run_cli(script, 'recall', '--query', 'Stop').stdout)
                self.assertEqual(len(rows), 2)
                start = self.run_cli(script, 'hook', payload=dict(session_id='s', hook_event_name='SessionStart', source='compact'))
                self.assertIn('Keep all responses', json.loads(start.stdout)['hookSpecificOutput']['additionalContext'])

    def test_hook_config_quotes_paths_and_does_not_install_settings(self):
        import shlex
        for host in ('codex', 'claude'):
            with self.subTest(host=host):
                script = self.script(host)
                config = json.loads(self.run_cli(script, 'hook-config').stdout)
                command = config['hooks']['PostToolUse'][0]['hooks'][0]['command']
                tokens = shlex.split(command)
                self.assertIn(str(self.root.resolve()), tokens)
                self.assertIn(str(script.resolve()), tokens)
                self.assertFalse((self.root / '.codex').exists())
                self.assertFalse((self.root / '.claude').exists())

    def test_batch_pending_and_get_preserve_overflowed_constraints(self):
        script = self.script('codex')
        self.run_cli(script, 'init', '--objective', 'Respect constraints')
        data = [{'id': f'c{i}', 'kind': 'constraint', 'actor': 'user', 'text': f'Constraint {i}: ' + 'long ' * 130} for i in range(24)]
        batch = self.root / 'batch.json'
        batch.write_text(json.dumps(data))
        self.run_cli(script, 'batch', '--file', str(batch))
        brief = self.run_cli(script, 'brief', '--max-bytes', '800').stdout
        self.assertIn('OVERFLOW', brief)
        first = json.loads(self.run_cli(script, 'pending', '--offset', '0', '--limit', '20').stdout)
        second = json.loads(self.run_cli(script, 'pending', '--offset', str(first['next_offset']), '--limit', '20').stdout)
        self.assertEqual(len(first['records']) + len(second['records']), 25)
        record = json.loads(self.run_cli(script, 'get', 'c23').stdout)
        self.assertEqual(record['text'], data[-1]['text'])

    def test_invalid_hook_input_reports_error_instead_of_clean_result(self):
        script = self.script('codex')
        self.run_cli(script, 'init', '--objective', 'Capture gaps')
        result = self.run_cli(script, 'hook', payload=['wrong envelope'])
        self.assertEqual(json.loads(result.stdout), {})
        rows = json.loads(self.run_cli(script, 'recall', '--query', 'Malformed').stdout)
        self.assertEqual(rows[0]['kind'], 'coverage')
        self.assertEqual(rows[0]['status'], 'unknown')

    def test_ignore_file_excludes_local_records_from_git(self):
        script = self.script('codex')
        self.run_cli(script, 'init', '--objective', 'Keep notes local')
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True, capture_output=True)
        result = subprocess.run(['git', '-C', str(self.root), 'status', '--porcelain'], check=True, capture_output=True, text=True)
        self.assertNotIn('.work-notes', result.stdout)

    def test_exact_multi_get_reduces_overflow_lookup_calls(self):
        script = self.script('codex')
        self.run_cli(script, 'init', '--objective', 'Retrieve exact records')
        self.run_cli(script, 'add', '--id', 'constraint', '--kind', 'constraint', '--text', 'Preserve API')
        result = json.loads(self.run_cli(script, 'get', 'objective', 'constraint').stdout)
        self.assertEqual([e['id'] for e in result], ['objective', 'constraint'])
        self.assertEqual(result[1]['text'], 'Preserve API')

    def test_task_inventory_restores_ids_without_guessing_latest(self):
        script = self.script('codex')
        self.run_cli(script, 'init', '--objective', 'First', task='first')
        self.run_cli(script, 'init', '--objective', 'Second', task='second')
        result = subprocess.run([sys.executable, str(script), '--root', str(self.root), 'tasks'],
                                capture_output=True, text=True, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({row['task'] for row in json.loads(result.stdout)}, {'first', 'second'})

    def test_exact_notes_invocation_is_not_recursively_recorded(self):
        import shlex
        script = self.script('codex')
        self.run_cli(script, 'init', '--objective', 'Avoid recursive notes')
        command = shlex.join([sys.executable, str(script.resolve()), '--root', str(self.root), '--task', 'retry', 'brief'])
        payload = dict(session_id='s', tool_use_id='own', hook_event_name='PostToolUse', tool_name='Bash',
                       tool_input={'command': command}, tool_response={'exit_code': 0, 'stdout': 'existing notes'})
        self.run_cli(script, 'hook', payload=payload)
        rows = json.loads(self.run_cli(script, 'pending').stdout)['records']
        self.assertEqual(len(rows), 1)
        payload['tool_use_id'] = 'mixed'
        payload['tool_input']['command'] += '; echo unrelated work'
        self.run_cli(script, 'hook', payload=payload)
        rows = json.loads(self.run_cli(script, 'pending').stdout)['records']
        self.assertEqual(len(rows), 2)


if __name__ == '__main__':
    unittest.main()
