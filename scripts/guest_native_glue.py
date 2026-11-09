"""Install exact self-owned native sources without overwriting upstream files."""
import hashlib
from pathlib import Path

from guest_input_resolver import native_glue_files
from guest_preparation_context import read_input


def install(root, source, guest):
    files = native_glue_files(guest)
    root, source = Path(root).resolve(strict=True), Path(source)
    if source.is_symlink():
        raise ValueError('native glue source tree is a symlink')
    source = source.resolve(strict=True)
    pending = []
    # Check every input and destination before writing any file. An upstream
    # addition or symlink is a conflict, even if its current bytes match ours.
    for destination, reference in files.items():
        data = read_input(root, reference['file'])
        if hashlib.sha256(data).hexdigest() != reference['sha256']:
            raise ValueError('native glue identity mismatch: ' + destination)
        target = source
        for component in destination.split('/'):
            target = target / component
            if target.is_symlink():
                raise ValueError('native glue destination symlink: ' + destination)
        if target.exists() or not target.parent.is_dir():
            raise ValueError('native glue destination conflict: ' + destination)
        pending.append((target, data))
    for target, data in pending:
        with target.open('xb') as stream:
            stream.write(data)
        target.chmod(0o644)
    return files
