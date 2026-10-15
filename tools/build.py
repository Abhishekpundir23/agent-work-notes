"""Build independent skill folders and reproducible archives without dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.0'


def generated(host):
    entry = f'#!/usr/bin/env python3\n"""Standalone {host} Work Notes entrypoint."""\nfrom notes_core import main\n\nif __name__ == "__main__":\n    raise SystemExit(main("{host}"))\n'
    return {'notes.py': entry.encode(),
            'notes_core.py': (ROOT / 'src/notes_core.py').read_bytes(),
            host + '_capture.py': (ROOT / 'src' / (host + '_capture.py')).read_bytes()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if bundled scripts differ from source; do not write')
    parser.add_argument('--zip', action='store_true', help='Write independent skill ZIPs in dist/')
    args = parser.parse_args()
    if args.check and args.zip:
        parser.error('--check and --zip cannot be combined')
    mismatches = []
    manifests = []
    for host in ('codex', 'claude'):
        skill = ROOT / 'skills' / (host + '-work-notes')
        scripts = skill / 'scripts'
        for name, content in generated(host).items():
            path = scripts / name
            if args.check:
                if not path.is_file() or path.read_bytes() != content:
                    mismatches.append(str(path.relative_to(ROOT)))
            else:
                scripts.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        if args.zip:
            output = ROOT / 'dist' / f'{host}-work-notes-{VERSION}.zip'
            output.parent.mkdir(exist_ok=True)
            with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(skill.rglob('*')):
                    if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                        continue
                    name = path.relative_to(skill.parent).as_posix()
                    info = zipfile.ZipInfo(name, date_time=(2026, 10, 15, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, path.read_bytes())
            manifests.append({'host': host, 'file': output.name,
                              'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                              'bytes': output.stat().st_size})
    if mismatches:
        print('Bundled scripts are stale:\n' + '\n'.join(mismatches), file=sys.stderr)
        return 1
    if args.zip:
        (ROOT / 'dist/manifest.json').write_text(json.dumps({'version': VERSION, 'archives': manifests}, indent=2) + '\n')
    print('Bundled scripts match source.' if args.check else 'Built two independent skill packages.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
