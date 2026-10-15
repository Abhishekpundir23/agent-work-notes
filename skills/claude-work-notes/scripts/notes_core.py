"""Local work records and consistent projections. Python standard library only."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
import uuid
from contextlib import contextmanager

VERSION = '0.1.0'
KINDS = {'objective', 'constraint', 'decision', 'action', 'check', 'question',
         'blocker', 'next', 'coverage', 'note'}
STATUSES = {'asserted', 'observed', 'attempted', 'running', 'passed', 'failed',
            'reverted', 'resolved', 'unknown'}
ACTORS = {'user', 'agent', 'tool', 'system'}
FIELDS = {'id', 'kind', 'text', 'actor', 'status', 'source', 'occurred_at',
          'evidence', 'depends_on', 'supersedes', 'metadata'}
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}\Z')
TASK = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def md(value):
    text = html.escape(str(value), quote=True).replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'([\\`*_\[\]|#])', r'\\\1', text)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def own_notes_command(payload, executable):
    """Recognize only a simple exact invocation, never a mixed shell command."""
    if not isinstance(payload, dict) or payload.get('tool_name') not in {'Bash', 'exec_command', 'shell'}:
        return False
    tool_input = payload.get('tool_input')
    command = tool_input.get('command', tool_input.get('cmd')) if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or any(char in command for char in ';\n\r|&`$<>'):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return (len(tokens) >= 2 and re.fullmatch(r'python(?:\d+(?:\.\d+)*)?', Path(tokens[0]).name) is not None
            and Path(tokens[1]).is_absolute() and Path(tokens[1]).resolve() == executable)


class Store:
    def __init__(self, root, host, task):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError('Project root must be an existing directory')
        if host not in {'codex', 'claude'}:
            raise ValueError('Host must be codex or claude')
        if not isinstance(task, str) or not TASK.fullmatch(task):
            raise ValueError('Task must be a 1–64 character name without slashes')
        self.host, self.task = host, task
        self.base = self.root / '.work-notes'
        self.directory = self.base / host
        if not self.directory.resolve().is_relative_to(self.root):
            raise ValueError('Work Notes state cannot resolve outside the project')
        self.db_path = self.directory / 'events.sqlite3'
        self.views = self.directory / 'views' / task

    def _open(self, create=False, check_task=True):
        if not create and not self.db_path.is_file():
            raise ValueError('No store exists; run init first')
        # Refuse symlinked databases or state after initialization as well.
        if self.db_path.is_symlink() or not self.db_path.resolve().is_relative_to(self.root):
            raise ValueError('Invalid database location')
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA busy_timeout=10000')
        if not create:
            meta = dict(conn.execute('SELECT key,value FROM meta').fetchall())
            if meta.get('root') != str(self.root) or meta.get('host') != self.host or meta.get('schema') != '1':
                conn.close()
                raise ValueError('Store root, host, or schema does not match this invocation')
            if check_task and not conn.execute('SELECT 1 FROM tasks WHERE task=?', (self.task,)).fetchone():
                conn.close()
                raise ValueError('Task is not initialized; run init for this task')
        return conn

    @contextmanager
    def _connect(self, create=False, check_task=True):
        conn = self._open(create, check_task)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self, objective):
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError('An objective is required')
        self.directory.mkdir(parents=True, exist_ok=True)
        ignore = self.base / '.gitignore'
        if not ignore.exists():
            ignore.write_text('*\n', encoding='utf-8')
        with self._connect(create=True) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks(task TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT NOT NULL, event_id TEXT NOT NULL,
                    payload TEXT NOT NULL, digest TEXT NOT NULL, previous TEXT NOT NULL,
                    recorded_at TEXT NOT NULL, UNIQUE(task,event_id));
                CREATE INDEX IF NOT EXISTS events_task ON events(task,seq);
                CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
                    BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
                CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
                    BEGIN SELECT RAISE(ABORT,'events are append-only'); END;
            ''')
            conn.execute('BEGIN IMMEDIATE')
            for key, value in {'root': str(self.root), 'host': self.host, 'schema': '1'}.items():
                row = conn.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
                if row and row[0] != value:
                    raise ValueError('Cannot initialize a store bound to another root/host/schema')
                conn.execute('INSERT OR IGNORE INTO meta VALUES(?,?)', (key, value))
            conn.execute('INSERT OR IGNORE INTO tasks VALUES(?)', (self.task,))
            result = self._append(conn, dict(id='objective', kind='objective', text=objective))
            conn.commit()
        return result

    def _path(self, value):
        if not isinstance(value, str) or not value or len(value) > 2048:
            raise ValueError('Evidence needs a nonempty root-relative path')
        path = Path(value)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Evidence must be relative to the project without traversal')
        if not (self.root / path).resolve().is_relative_to(self.root):
            raise ValueError('Evidence path resolves outside the project')
        return path.as_posix()

    def _normalize(self, value):
        if not isinstance(value, dict) or set(value) - FIELDS:
            raise ValueError('Event must contain only documented fields')
        event = dict(id=value.get('id', 'e-' + uuid.uuid4().hex), kind=value.get('kind'),
                     text=value.get('text'), actor=value.get('actor', 'agent'),
                     status=value.get('status', 'asserted'), source=value.get('source', ''),
                     occurred_at=value.get('occurred_at'), evidence=value.get('evidence', []),
                     depends_on=value.get('depends_on', []), supersedes=value.get('supersedes', []),
                     metadata=value.get('metadata', {}))
        if not isinstance(event['id'], str) or not IDENT.fullmatch(event['id']):
            raise ValueError('Invalid event ID')
        if event['kind'] not in KINDS or event['status'] not in STATUSES or event['actor'] not in ACTORS:
            raise ValueError('Unknown event kind, status, or actor')
        if not isinstance(event['text'], str) or not event['text'].strip() or len(event['text'].encode('utf-8')) > 16000:
            raise ValueError('Event text must be nonempty and at most 16000 UTF-8 bytes')
        if not isinstance(event['source'], str) or len(event['source']) > 2048:
            raise ValueError('Source must be a string of at most 2048 characters')
        if event['occurred_at'] is not None:
            if not isinstance(event['occurred_at'], str) or len(event['occurred_at']) > 80:
                raise ValueError('occurred_at must be a source timestamp string or null')
        if not isinstance(event['metadata'], dict) or len(canonical(event['metadata']).encode()) > 8192:
            raise ValueError('metadata must be a JSON object of at most 8192 bytes')
        for key in ('depends_on', 'supersedes'):
            refs = event[key]
            if not isinstance(refs, list) or len(refs) > 100 or any(not isinstance(r, str) or not IDENT.fullmatch(r) for r in refs):
                raise ValueError(f'{key} must be a list of at most 100 event IDs')
            event[key] = sorted(set(refs))
        if not isinstance(event['evidence'], list) or len(event['evidence']) > 100:
            raise ValueError('evidence must be a list of at most 100 exact file references')
        evidence = []
        for ref in event['evidence']:
            if not isinstance(ref, dict) or set(ref) - {'path', 'sha256'}:
                raise ValueError('Evidence allows path and optional sha256 only')
            cleaned = {'path': self._path(ref.get('path'))}
            if 'sha256' in ref:
                if not isinstance(ref['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', ref['sha256']):
                    raise ValueError('Invalid SHA-256 evidence digest')
                cleaned['sha256'] = ref['sha256']
            evidence.append(cleaned)
        event['evidence'] = evidence
        # JSON round trip removes aliases and rejects non-JSON input before any write.
        return json.loads(canonical(event))

    @staticmethod
    def _semantic(event):
        event = json.loads(canonical(event))
        event['metadata'].pop('captured_at', None)
        return event

    def _append(self, conn, value):
        event = self._normalize(value)
        row = conn.execute('SELECT * FROM events WHERE task=? AND event_id=?', (self.task, event['id'])).fetchone()
        if row:
            if self._semantic(json.loads(row['payload'])) != self._semantic(event):
                raise ValueError('Event ID already exists with different content; append a new event')
            return self._decode(row)
        for key in ('depends_on', 'supersedes'):
            for ident in event[key]:
                row = conn.execute('SELECT payload FROM events WHERE task=? AND event_id=?', (self.task, ident)).fetchone()
                if not row:
                    raise ValueError(f'{key} references an unknown event in this task: {ident}')
                prior = json.loads(row[0])
                if key == 'supersedes':
                    if prior['kind'] != event['kind']:
                        raise ValueError('A correction must use the same event kind')
                    if prior['actor'] == 'user' and prior['kind'] in {'objective', 'constraint', 'decision'} and event['actor'] != 'user':
                        raise ValueError('A non-user assertion cannot replace this user requirement')
        row = conn.execute('SELECT digest FROM events WHERE task=? ORDER BY seq DESC LIMIT 1', (self.task,)).fetchone()
        previous = row[0] if row else ''
        payload = canonical(event)
        digest = hashlib.sha256((previous + '\n' + payload).encode()).hexdigest()
        cur = conn.execute('INSERT INTO events(task,event_id,payload,digest,previous,recorded_at) VALUES(?,?,?,?,?,?)',
                           (self.task, event['id'], payload, digest, previous, now()))
        return self._decode(conn.execute('SELECT * FROM events WHERE seq=?', (cur.lastrowid,)).fetchone())

    @staticmethod
    def _decode(row):
        return dict(json.loads(row['payload']), seq=row['seq'], recorded_at=row['recorded_at'], digest=row['digest'])

    def append(self, event):
        return self.append_many([event])[0]

    def append_many(self, events):
        if not isinstance(events, list) or len(events) > 1000:
            raise ValueError('Batch must be a JSON array of at most 1000 events')
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            results = [self._append(conn, event) for event in events]
            conn.commit()
        return results

    def events(self):
        with self._connect() as conn:
            return [self._decode(row) for row in conn.execute('SELECT * FROM events WHERE task=? ORDER BY seq', (self.task,))]

    def get(self, ident):
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM events WHERE task=? AND event_id=?', (self.task, ident)).fetchone()
        if not row:
            raise ValueError('Event does not exist in this task')
        return self._decode(row)

    def tasks(self):
        with self._connect(check_task=False) as conn:
            return [dict(row) for row in conn.execute(
                'SELECT task,MAX(seq) AS revision,MAX(recorded_at) AS last_recorded_at FROM events GROUP BY task ORDER BY task')]

    def state(self, events=None):
        events = self.events() if events is None else events
        replaced = {ident for e in events for ident in e['supersedes']}
        active = [e for e in events if e['id'] not in replaced]
        active_ids = {e['id'] for e in active}
        stale = set()
        # References always point backwards; iteration also handles transitive invalidation.
        for event in events:
            if any(ref not in active_ids or ref in stale for ref in event['depends_on']):
                stale.add(event['id'])
        # Propagate only active terminal IDs backwards. A linear chain carries
        # one ID per event, rather than copying its entire historical ancestry.
        descendants = {event['id']: {event['id']} for event in active}
        for event in reversed(events):
            heads = descendants.get(event['id'], set())
            for parent in event['supersedes']:
                descendants.setdefault(parent, set()).update(heads)
        pairs = set()
        for group in descendants.values():
            group = sorted(group)
            for i, left in enumerate(group):
                for right in group[i+1:]:
                    pairs.add(tuple(sorted((left, right))))
        conflicts = [list(pair) for pair in sorted(pairs)]
        return dict(revision=events[-1]['seq'] if events else 0, active=active,
                    stale=sorted(stale & active_ids), conflicts=conflicts,
                    coverage='partial', total=len(events))

    def recall(self, query, limit=8):
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('Recall limit must be between 1 and 100')
        events = self.events()
        by_id = {e['id']: e for e in events}
        children = {}
        for event in events:
            for parent in event['supersedes']:
                children.setdefault(parent, []).append(event['id'])
        matched = [e['id'] for e in events if query.casefold() in e['text'].casefold() or query == e['id']]
        terminal = set()
        stack = matched[:]
        seen = set()
        while stack:
            ident = stack.pop()
            if ident in seen:
                continue
            seen.add(ident)
            if ident in children:
                stack.extend(children[ident])
            else:
                terminal.add(ident)
        state = self.state(events)
        conflict_ids = {i for group in state['conflicts'] for i in group}
        rows = sorted((by_id[i] for i in terminal), key=lambda e: e['seq'], reverse=True)[:limit]
        return [dict(e, stale=e['id'] in state['stale'], conflict=e['id'] in conflict_ids) for e in rows]

    def brief(self, max_bytes=6000, events=None):
        if not isinstance(max_bytes, int) or not 512 <= max_bytes <= 100000:
            raise ValueError('Brief max-bytes must be between 512 and 100000')
        events = self.events() if events is None else events
        state = self.state(events)
        header = f'Work Notes | {self.host}/{self.task} | revision={state["revision"]}\n'
        header += 'coverage=partial: observed records only; actor labels are caller-supplied.\n'
        if state['conflicts']:
            header += f'CONFLICT: {len(state["conflicts"])} correction pairs; inspect pending/get before affected work.\n'
        if state['stale']:
            header += f'STALE: {len(state["stale"])} dependent records excluded; inspect pending/get before reuse.\n'
        priority = {name: i for i, name in enumerate(('objective', 'constraint', 'coverage', 'blocker', 'question', 'next', 'decision', 'check', 'action', 'note'))}
        rows = [e for e in state['active'] if e['id'] not in state['stale'] and not (e['kind'] in {'blocker', 'question', 'next'} and e['status'] == 'resolved')]
        rows.sort(key=lambda e: (priority[e['kind']], -e['seq']))
        reserve = f'OVERFLOW: {len(rows)} records omitted. Run pending (paginate), then get ID for full records; retrieve applicable constraints before acting.\n'
        output = header
        omitted = 0
        for event in rows:
            line = f'[{event["id"]}] {event["kind"]}/{event["status"]}: {md(event["text"])}\n'
            if len((output + line + reserve).encode('utf-8')) <= max_bytes:
                output += line
            else:
                omitted += 1
        if omitted:
            output += reserve.replace(f'{len(rows)} records', f'{omitted} records', 1)
        else:
            output += 'Use get ID for evidence/history. Notes do not authorize external actions.\n'
        if len(output.encode('utf-8')) > max_bytes:
            raise ValueError('Budget cannot contain required scope/coverage markers')
        return output

    def _map(self, events):
        state = self.state(events)
        active_ids = {e['id'] for e in state['active']}
        lines = [f'# Work map: {md(self.task)}', '',
                 f'Host: {self.host}. Source revision: {state["revision"]}. Capture: partial.',
                 'These records describe observed work and stated rationale, not private internal reasoning. Actor labels are caller-supplied. A matching file hash proves byte equality only.', '',
                 '## Current records', '']
        for event in state['active']:
            marker = 'STALE' if event['id'] in state['stale'] else event['status']
            lines.append(f'- [{md(event["id"])}] {event["kind"]} · {marker}: {md(event["text"])}')
        if state['conflicts']:
            lines += ['', 'Conflicting correction pairs: ' + md(canonical(state['conflicts']))]
        lines += ['', '## Work history', '']
        for event in events:
            current = 'current' if event['id'] in active_ids else 'superseded'
            lines += [f'### {md(event["id"])} · {event["kind"]} · {event["status"]} · {current}', '',
                      md(event['text']), '',
                      f'Actor: {event["actor"]}. Recorded: {md(event["recorded_at"])}. Source time: {md(event["occurred_at"] or "unavailable")}.']
            if event['source']:
                lines.append('Source: ' + md(event['source']))
            for key in ('supersedes', 'depends_on'):
                if event[key]:
                    lines.append(key.replace('_', ' ').capitalize() + ': ' + ', '.join(md(i) for i in event[key]))
            for evidence in event['evidence']:
                lines.append('Evidence path: ' + md(evidence['path']) + '; SHA-256: ' + evidence.get('sha256', 'not recorded'))
            if event['metadata']:
                lines.append('Metadata: ' + md(canonical(event['metadata'])))
            lines.append('')
        lines += ['## Relationship map', '', '```mermaid', 'flowchart TD']
        seq = {e['id']: e['seq'] for e in events}
        for event in events:
            # Diagram labels contain only validated IDs and enumerated kinds, never arbitrary text.
            lines.append(f'  n{event["seq"]}["{event["id"]}: {event["kind"]}"]')
            for ref in event['supersedes']:
                lines.append(f'  n{seq[ref]} -->|corrected by| n{event["seq"]}')
            for ref in event['depends_on']:
                lines.append(f'  n{seq[ref]} -->|supports| n{event["seq"]}')
        lines += ['```', '']
        return '\n'.join(lines)

    def render(self, max_bytes=6000):
        events = self.events()
        revision = self.state(events)['revision']
        brief = self.brief(max_bytes, events)
        work_map = self._map(events)
        self.views.mkdir(parents=True, exist_ok=True)
        destination = self.views / f'r{revision}-b{max_bytes}'
        manifest = dict(schema=1, version=VERSION, host=self.host, task=self.task, revision=revision,
                        max_bytes=max_bytes, brief_bytes=len(brief.encode()), token_estimate_method='UTF-8 bytes / 4; not tokenizer exact',
                        estimated_brief_tokens=(len(brief.encode()) + 3) // 4,
                        last_event_digest=events[-1]['digest'],
                        brief_sha256=hashlib.sha256(brief.encode()).hexdigest(),
                        map_sha256=hashlib.sha256(work_map.encode()).hexdigest())
        temporary = Path(tempfile.mkdtemp(prefix='.render-', dir=self.views))
        try:
            (temporary / 'brief.md').write_text(brief, encoding='utf-8')
            (temporary / 'map.md').write_text(work_map, encoding='utf-8')
            (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
            try:
                temporary.rename(destination)
            except OSError:
                if not destination.is_dir() or (destination / 'manifest.json').read_text() != (temporary / 'manifest.json').read_text():
                    raise
                if hash_file(destination / 'brief.md') != manifest['brief_sha256'] or hash_file(destination / 'map.md') != manifest['map_sha256']:
                    raise ValueError('Generated view was modified; preserve/move that revision directory before rendering again')
            with self._connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                pointer = self.views / 'current.json'
                prior = json.loads(pointer.read_text()) if pointer.exists() else {}
                if prior.get('revision', 0) <= revision:
                    atomic_json(pointer, dict(revision=revision, directory=destination.name))
                conn.commit()
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return dict(brief=str(destination / 'brief.md'), map=str(destination / 'map.md'),
                    manifest=str(destination / 'manifest.json'), revision=revision)

    def doctor(self):
        ledger_errors = []
        with self._connect() as conn:
            rows = list(conn.execute('SELECT * FROM events WHERE task=? ORDER BY seq', (self.task,)))
        previous = ''
        for row in rows:
            expected = hashlib.sha256((previous + '\n' + row['payload']).encode()).hexdigest()
            if row['previous'] != previous or row['digest'] != expected:
                ledger_errors.append(f'History digest mismatch at {row["event_id"]}')
            previous = row['digest']
        evidence = []
        for row in rows:
            for ref in json.loads(row['payload'])['evidence']:
                item = dict(event_id=row['event_id'], path=ref['path'])
                try:
                    path = self.root / self._path(ref['path'])
                    if not path.is_file():
                        item['state'] = 'missing'
                    elif 'sha256' not in ref:
                        item['state'] = 'present_without_digest'
                    else:
                        item['state'] = 'unchanged' if hash_file(path) == ref['sha256'] else 'changed'
                except (OSError, ValueError) as exc:
                    item.update(state='unavailable', error=str(exc))
                evidence.append(item)
        revision = rows[-1]['seq'] if rows else 0
        view_stale = True
        view_errors = []
        pointer = self.views / 'current.json'
        if pointer.exists():
            try:
                current = json.loads(pointer.read_text())
                if not re.fullmatch(r'r\d+-b\d+', current['directory']):
                    raise ValueError('Invalid view directory')
                path = self.views / current['directory']
                manifest = json.loads((path / 'manifest.json').read_text())
                view_stale = current['revision'] != revision or manifest['revision'] != revision
                for filename, key in (('brief.md', 'brief_sha256'), ('map.md', 'map_sha256')):
                    if hash_file(path / filename) != manifest[key]:
                        view_errors.append(f'Changed generated view: {filename}')
            except (OSError, ValueError, KeyError) as exc:
                view_errors.append(str(exc))
        return dict(task=self.task, host=self.host, revision=revision, coverage='partial',
                    ledger_errors=ledger_errors, evidence=evidence, view_stale=view_stale,
                    view_errors=view_errors, note='Integrity and file state checks do not prove truth, authorship, or task completion.')


def main(host, argv=None):
    parser = argparse.ArgumentParser(description=f'Work Notes {VERSION} — independent {host} work records')
    parser.add_argument('--root', default='.', help='Project root (default: current directory)')
    parser.add_argument('--task', help='Explicit task identifier; required except for tasks inventory')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init'); init.add_argument('--objective', required=True)
    add = commands.add_parser('add')
    add.add_argument('--id'); add.add_argument('--kind', choices=sorted(KINDS), required=True)
    add.add_argument('--text', required=True); add.add_argument('--actor', choices=sorted(ACTORS), default='agent')
    add.add_argument('--status', choices=sorted(STATUSES), default='asserted'); add.add_argument('--source', default='')
    for flag in ('file', 'supersedes', 'depends-on'):
        add.add_argument('--' + flag, action='append', default=[])
    batch = commands.add_parser('batch'); batch.add_argument('--file', required=True)
    for name in ('brief', 'render'):
        command = commands.add_parser(name); command.add_argument('--max-bytes', type=int, default=6000)
    get = commands.add_parser('get'); get.add_argument('ids', nargs='+')
    recall = commands.add_parser('recall'); recall.add_argument('--query', required=True); recall.add_argument('--limit', type=int, default=8)
    pending = commands.add_parser('pending'); pending.add_argument('--offset', type=int, default=0); pending.add_argument('--limit', type=int, default=20)
    commands.add_parser('doctor'); commands.add_parser('hook'); commands.add_parser('hook-config'); commands.add_parser('tasks')
    args = parser.parse_args(argv)
    if not args.task and args.command != 'tasks':
        parser.error('--task is required for this command; use tasks to inspect existing IDs')
    try:
        store = Store(args.root, host, args.task or 'inventory')
        if args.command == 'tasks':
            result = store.tasks()
        elif args.command == 'init':
            event = store.initialize(args.objective); result = {'id': event['id'], 'revision': event['seq']}
        elif args.command == 'add':
            event = dict(kind=args.kind, text=args.text, actor=args.actor, status=args.status,
                         source=args.source, supersedes=args.supersedes, depends_on=args.depends_on)
            if args.id:
                event['id'] = args.id
            event['evidence'] = [{'path': store._path(p), 'sha256': hash_file(store.root / store._path(p))} for p in args.file]
            value = store.append(event); result = {'id': value['id'], 'revision': value['seq']}
        elif args.command == 'batch':
            events = json.loads(Path(args.file).read_text(encoding='utf-8'))
            result = [{'id': e['id'], 'revision': e['seq']} for e in store.append_many(events)]
        elif args.command == 'brief':
            sys.stdout.write(store.brief(args.max_bytes)); return 0
        elif args.command == 'render':
            result = store.render(args.max_bytes)
        elif args.command == 'get':
            if len(args.ids) > 100:
                raise ValueError('Retrieve at most 100 exact records per call')
            values = [store.get(ident) for ident in args.ids]
            result = values[0] if len(values) == 1 else values
        elif args.command == 'recall':
            result = store.recall(args.query, args.limit)
        elif args.command == 'pending':
            if args.offset < 0 or not 1 <= args.limit <= 100:
                raise ValueError('offset must be nonnegative and limit between 1 and 100')
            state = store.state(); rows = state['active'][args.offset:args.offset + args.limit]
            result = dict(revision=state['revision'], conflicts=state['conflicts'], stale=state['stale'],
                          records=[{k: e[k] for k in ('id', 'kind', 'status')} | {'preview': e['text'][:120]} for e in rows],
                          next_offset=args.offset + args.limit if args.offset + args.limit < len(state['active']) else None)
        elif args.command == 'doctor':
            result = store.doctor()
        elif args.command == 'hook-config':
            executable = str(Path(sys.argv[0]).resolve())
            command = shlex.join([sys.executable, executable, '--root', str(store.root), '--task', store.task, 'hook'])
            names = ['SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop', 'PreCompact']
            names += ['PostToolUseFailure', 'StopFailure'] if host == 'claude' else ['Interrupt']
            result = {'hooks': {name: [{'hooks': [{'type': 'command', 'command': command, 'timeout': 10}]}] for name in names}}
        else:
            # Bound stdin before JSON parsing. The host receives a nonzero exit on capture failure.
            raw = sys.stdin.buffer.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Hook payload exceeds 2 MB; capture incomplete')
            payload = json.loads(raw)
            if own_notes_command(payload, Path(sys.argv[0]).resolve()):
                print('{}')
                return 0
            if host == 'codex':
                from codex_capture import normalize
            else:
                from claude_capture import normalize
            owned = [store.db_path, Path(str(store.db_path) + '-wal'), Path(str(store.db_path) + '-shm'),
                     store.base / '.gitignore', Path(sys.argv[0]).resolve()]
            if store.views.is_dir():
                owned.extend(path for path in store.views.rglob('*') if path.is_file())
            captured = normalize(payload, store.root, owned_paths=tuple(owned))
            store.append_many(captured)
            if isinstance(payload, dict) and payload.get('hook_event_name') == 'SessionStart':
                result = {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': store.brief()}}
            else:
                result = {}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error, TypeError) as exc:
        print('Work Notes error: ' + str(exc), file=sys.stderr)
        return 1
