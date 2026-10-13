#!/usr/bin/env python3
"""Copy this prepared project to a new durable workspace, then rebuild there."""
import argparse
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    if 'ur_gz' in destination.parts:
        parser.error('Destination must be separate from ur_gz.')
    if destination == source or source in destination.parents or destination in source.parents:
        parser.error('Source and destination must not overlap.')
    if destination.exists() and any(destination.iterdir()):
        parser.error('Refusing to overwrite a nonempty destination.')
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {'build', 'install', 'log', '.git', '.runtime', '__pycache__'}
    for path in source.iterdir():
        if path.name in excluded:
            continue
        target = destination / path.name
        if path.is_dir():
            shutil.copytree(path, target, symlinks=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(path, target)
    # Only extracted dependencies are portable; transient logs/PIDs/caches stay out.
    underlay = source / '.runtime' / 'underlay'
    if underlay.exists():
        shutil.copytree(underlay, destination / '.runtime' / 'underlay', symlinks=True)
    print('Copied to', destination)
    print('Run bash scripts/build.sh in that directory; old build/install are intentionally omitted.')


if __name__ == '__main__':
    main()
