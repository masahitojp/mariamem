#!/usr/bin/env python3
"""Fetch and verify only this native probe's pinned inputs (Python 3.12+)."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
import urllib.request
import zipfile

root = Path(sys.argv[1]).resolve()
repo = Path(__file__).resolve().parents[3]
lock = json.loads((repo/'release/inputs.lock.json').read_text())
root.mkdir(parents=True, exist_ok=True)
for name in ['mariadb', 'libmariadb', 'libfmt']:
    item = next(i for i in lock['inputs'] if i['name'] == name)
    archive = root/item['file']
    if not archive.exists():
        urllib.request.urlretrieve(item['url'], archive)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == item['sha256'], name
    print(name, 'verified', flush=True)
    if name == 'libfmt':
        with zipfile.ZipFile(archive) as z:
            z.extractall(root)
    else:
        target = root/('source' if name == 'mariadb' else 'connector')
        target.mkdir(exist_ok=True)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if len(parts) < 2:
                    continue
                member.name = str(Path(*parts[1:]))
                tar.extract(member, target, filter='data')
shutil.rmtree(root/'source/libmariadb')
shutil.move(root/'connector', root/'source/libmariadb')
