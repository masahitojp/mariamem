"""Reuse only the authenticated native reference from Ubuntu CI43137408120."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

RUN = 43137408120
ARTIFACT = 13908017919
SOURCE = 'a197034c6dabd663c84262323d6b42c5c20fb2a2'
ZIP_SHA256 = '895a25a0df71274629ebdf3550e6032ce1f8aaa26f622bef909b789d046b27ef'
NATIVE_SHA256 = '1e50fe15df475c29a3d58c9192106b0e890e104c4f2dde8ddc6118caa86e3c81'


def verified_reference(archive):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ZIP_SHA256:
        raise ValueError('Ubuntu reference ZIP checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('duplicate reference archive members')
        if json.loads(z.read('source.json'))['source_commit'] != SOURCE:
            raise ValueError('Ubuntu reference source mismatch')
        native = z.read('native.json')
        digest = hashlib.sha256(native).hexdigest()
        if digest != NATIVE_SHA256 or json.loads(z.read('SHA256SUMS.json'))['native.json'] != digest:
            raise ValueError('native reference checksum mismatch')
    return native


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    native = verified_reference(a.archive)
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'native.json').write_bytes(native)
    (a.output/'native-reuse.json').write_text(json.dumps({
        'run': RUN, 'artifact': ARTIFACT, 'source_commit': SOURCE,
        'zip_sha256': ZIP_SHA256, 'native_sha256': NATIVE_SHA256,
        'native_server_platform': 'Ubuntu 24.04 x86_64',
        'native_rerun_on_mac': False,
    }, indent=2)+'\n')


if __name__ == '__main__':
    main()
