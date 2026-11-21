"""Restore the campaign's JSON observations from the lossless per-condition archives."""
import gzip
from pathlib import Path
import re
import sys
import tarfile

root=Path(sys.argv[1])
target=root/'runs'
target.mkdir(exist_ok=True)
seen=set()
for archive in sorted((root/'observations').glob('*.tar.xz')):
    with tarfile.open(archive,'r:xz') as t:
        for m in t:
            assert m.isfile() and re.fullmatch(r'(main|warm)-\d{3}-\d-(diag|raw)-(400|50)-(default|off)\.json',m.name)
            assert m.name not in seen
            seen.add(m.name)
            dest=target/(m.name+'.gz')
            data=t.extractfile(m).read()
            if dest.exists():
                assert gzip.decompress(dest.read_bytes())==data
            else:dest.write_bytes(gzip.compress(data,compresslevel=1,mtime=0))
assert len(seen)==582
