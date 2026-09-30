"""Private exact-tag Go module fixtures; never create a remote tag or release."""
import hashlib
import json
from pathlib import Path
import zipfile

MODULE = 'github.com/masahitojp/mariamem'


def source_files(root):
    root = Path(root)
    paths = sorted(p for base in (root, root / 'internal') for p in
                   (base.glob('*.go') if base == root else base.rglob('*.go'))
                   if not p.name.endswith('_test.go'))
    return paths + [root / name for name in ('go.mod', 'go.sum', 'LICENSE', 'release/inputs.lock.json')]


def source_identity(root):
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in source_files(root)}
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def prepare_proxy(root, work, tag):
    directory = work / 'proxy' / MODULE / '@v'
    directory.mkdir(parents=True)
    (directory / f'{tag}.mod').write_bytes((root / 'go.mod').read_bytes())
    (directory / f'{tag}.info').write_text(json.dumps({'Version': tag, 'Time': '2026-09-29T00:00:00Z'}))
    (directory / 'list').write_text(tag + '\n')
    with zipfile.ZipFile(directory / f'{tag}.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(root):
            archive.write(path, f'{MODULE}@{tag}/{path.relative_to(root).as_posix()}')
    return work / 'proxy'
