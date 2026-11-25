"""Stage complete artifact directories, then exchange them atomically."""
import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path

SNAPSHOT_FILES = ('catalog.json', 'observations.json', 'manifest.json')
RECORD = 'data/publication.json'


def validate_snapshot_destination(output):
    path = Path(output).absolute()
    for component in (*reversed(path.parents), path):
        if component.is_symlink():
            raise ValueError(f'Snapshot destination contains a symlink: {component}')
    path = path.resolve()
    if path.exists():
        if not path.is_dir():
            raise ValueError(f'Snapshot destination must be a directory: {path}')
        names = set()
        for entry in path.iterdir():
            if entry.name not in SNAPSHOT_FILES or entry.is_symlink() or not entry.is_file():
                raise ValueError(f'Unexpected entry in snapshot destination: {entry}')
            names.add(entry.name)
        missing = set(SNAPSHOT_FILES) - names
        if names and missing:
            raise ValueError(f'Incomplete snapshot destination {path}; missing {", ".join(sorted(missing))}')
    return path


def replace_directory(stage, output):
    stage, output = Path(stage), Path(output)
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError('Artifact output must be a regular directory')
    if not output.exists():
        os.replace(stage, output)
        return
    # Exchange two directories in one syscall: readers never see a missing or
    # partially written snapshot. The previous directory is cleaned with staging.
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin':
        result = libc.renameatx_np(-2, os.fsencode(stage), -2, os.fsencode(output), 2)
    elif sys.platform.startswith('linux') and hasattr(libc, 'renameat2'):
        result = libc.renameat2(-100, os.fsencode(stage), -100, os.fsencode(output), 2)
    else:
        raise ValueError('Atomic directory exchange requires macOS or Linux renameat2')
    if result:
        raise OSError(ctypes.get_errno(), 'Atomic artifact exchange failed')


def write_documents(directory, documents):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, document in zip(SNAPSHOT_FILES, documents):
        (directory / name).write_text(
            json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def promote_snapshot(output, documents):
    output = validate_snapshot_destination(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'snapshot'
        write_documents(stage, documents)
        validate_snapshot_destination(output)
        replace_directory(stage, output)
