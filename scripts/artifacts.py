"""Stage complete artifact directories, then exchange them atomically."""
import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path


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
    for name, document in zip(('catalog', 'observations', 'manifest'), documents):
        (directory / f'{name}.json').write_text(
            json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def promote_snapshot(output, documents):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'snapshot'
        write_documents(stage, documents)
        replace_directory(stage, output)
