#!/usr/bin/env python3
"""Package source, configuration and measured maps; report/video stay separate."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
required = ['maps/map.yaml', 'maps/map.pgm', 'README.md']
missing = [name for name in required if not (root / name).is_file()]
if missing:
    raise SystemExit('Submission is incomplete: ' + ', '.join(missing))
output = root / 'submission/tb4_lab_23020732.zip'
output.parent.mkdir(exist_ok=True)
temporary = output.with_suffix('.zip.tmp')
excluded = {'__pycache__', '.pytest_cache', '.git'}
files = [root / name for name in ['.gitignore', 'LICENSE', 'README.md', 'THIRD_PARTY.md']]
for directory in ['src', 'scripts', 'maps']:
    files.extend(sorted((root / directory).rglob('*')))
with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        relative = path.relative_to(root)
        if any(part in excluded for part in relative.parts):
            continue
        if path.is_symlink():
            raise SystemExit('Refusing source symlink: ' + str(relative))
        if path.is_file() and path.suffix.lower() not in {'.pyc', '.zip'}:
            archive.write(path, str(Path('workspace') / relative))
with zipfile.ZipFile(temporary) as archive:
    if archive.testzip() is not None:
        raise SystemExit('ZIP validation failed')
temporary.replace(output)
print(output)
