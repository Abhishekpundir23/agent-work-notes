"""Measure local storage/render overhead; this is not an agent usefulness benchmark."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from notes_core import Store


def run(count):
    with tempfile.TemporaryDirectory(prefix='work-notes-benchmark-') as directory:
        store = Store(directory, 'codex', 'synthetic')
        store.initialize('Inspect and repair retries; preserve existing public behavior')
        store.append({'id': 'constraint', 'kind': 'constraint', 'actor': 'user', 'text': 'Do not deploy without explicit approval'})
        start = time.perf_counter()
        for offset in range(0, count, 1000):
            store.append_many([{'id': f'action-{i}', 'kind': 'action', 'status': 'observed',
                                'text': f'Observed synthetic tool action {i}; detailed source remains available at its event reference.'}
                               for i in range(offset, min(offset + 1000, count))])
        append_seconds = time.perf_counter() - start
        start = time.perf_counter()
        brief = store.brief(6000)
        brief_seconds = time.perf_counter() - start
        start = time.perf_counter()
        views = store.render(6000)
        render_seconds = time.perf_counter() - start
        assert len(brief.encode()) <= 6000
        assert 'Do not deploy without explicit approval' in brief
        return {'events': count + 2, 'append_seconds': append_seconds,
                'brief_seconds': brief_seconds, 'render_seconds': render_seconds,
                'brief_bytes': len(brief.encode()), 'map_bytes': Path(views['map']).stat().st_size,
                'database_bytes': store.db_path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events', type=int, default=5000)
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 1 <= args.events <= 100000 or not 1 <= args.runs <= 10:
        parser.error('events must be 1..100000; runs 1..10')
    runs = [run(args.events) for _ in range(args.runs)]
    result = {'scope': 'Synthetic local storage/render timing only; excludes host/model/token overhead and task success.',
              'python': platform.python_version(), 'platform': platform.system() + ' ' + platform.machine(),
              'runs': runs, 'median_seconds': {key: statistics.median(r[key] for r in runs) for key in ('append_seconds', 'brief_seconds', 'render_seconds')}}
    output = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    print(output)


if __name__ == '__main__':
    main()
