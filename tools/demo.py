"""Generate checked-in sample views from synthetic history, without a live agent."""
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from notes_core import Store


def main():
    events = json.loads((ROOT / 'examples/retry-events.json').read_text())
    with tempfile.TemporaryDirectory(prefix='work-notes-demo-') as directory:
        store = Store(directory, 'codex', 'retry-example')
        store.initialize('Fix retry timeout behavior')
        store.append_many(events)
        views = store.render(max_bytes=2500)
        for key, name in (('brief', 'retry-brief.md'), ('map', 'retry-map.md'), ('manifest', 'retry-manifest.json')):
            shutil.copyfile(views[key], ROOT / 'examples' / name)
        doctor = store.doctor()
        if doctor['ledger_errors'] or doctor['view_errors'] or doctor['view_stale']:
            raise RuntimeError('Synthetic demo failed integrity checks')
    print('Generated synthetic example brief and map; no actual project task was performed.')


if __name__ == '__main__':
    main()
