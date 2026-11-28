"""Fail-closed canonical history-wait source contract; native tests run on preparation."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = b'--- a/tpool/tpool.h\n'
BASE_SHA256 = '0826197caa46c8d1e389e9883e752749b99eb84a56b0afee48b7ba6dd2465288'
DELTA_SHA256 = '5b9aaf3417bce2cf59d78ae388e72ef8d8abae0ab0990c11361c7bc9af7a480f'


def source(root=ROOT):
    root = Path(root)
    if (root/'guest/experimental.patch').exists():
        raise ValueError('history wait must be canonical')
    patch = (root/'guest/source.patch').read_bytes()
    if patch.count(BOUNDARY) != 1:
        raise ValueError('history wait boundary missing/duplicate')
    base, tail = patch.split(BOUNDARY)
    if (hashlib.sha256(base).hexdigest() != BASE_SHA256 or
            hashlib.sha256(BOUNDARY+tail).hexdigest() != DELTA_SHA256):
        raise ValueError('reviewed history wait source changed')
    return {'base_sha256': BASE_SHA256, 'history_delta_sha256': DELTA_SHA256}


if __name__ == '__main__':
    print(source())
