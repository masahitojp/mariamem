"""Fetch a bounded set of immutable upstream files; preserve identities only."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

evidence = Path(__file__).resolve().parent
plan = json.loads((evidence / 'native-plan.json').read_text())
dest = evidence.parent / 'temp' / 'upstream'
manifest_path = evidence / 'source-files.json'
records = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
for name in sys.argv[1:]:
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    prior = next((r for r in records if r['path'] == name), None)
    assert prior is not None or len(records) < plan['maximum_files']
    response = subprocess.run(
        ['gh', 'api', 'repos/MariaDB/server/contents/' + name + '?ref=' + plan['source_commit']],
        check=True, capture_output=True, timeout=30,
    )
    row = json.loads(response.stdout)
    assert row['encoding'] == 'base64'
    data = base64.b64decode(row['content'])
    assert len(data) == row['size']
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert blob == row['sha']
    record = dict(path=name, source_commit=plan['source_commit'], github_blob=blob,
                  sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    if prior is not None:
        assert prior == record
    else:
        records.append(record)
    target = dest / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    manifest_path.write_text(json.dumps(records, indent=2) + '\n')
    print(name, len(data), flush=True)
