"""Read-only identity/anchor replay; does not prove runtime performance."""
import hashlib
import json
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
upstream, worktree = map(Path, sys.argv[1:])
for row in json.loads((here / 'source-files.json').read_text()):
    data = (upstream / row['path']).read_bytes()
    assert len(data) == row['bytes'], row['path']
    assert hashlib.sha256(data).hexdigest() == row['sha256'], row['path']
    assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == row['github_blob'], row['path']
for row in json.loads((here / 'anchors.json').read_text()):
    lines = (upstream / row['path']).read_text().splitlines()
    excerpt = '\n'.join(lines[row['start_line'] - 1:row['end_line']]) + '\n'
    assert hashlib.sha256(excerpt.encode()).hexdigest() == row['excerpt_sha256'], row
mapping = json.loads((here / 'generated-mapping.json').read_text())
data = (worktree / 'internal/generatedgo/code/p2/p2_pure.go').read_bytes()
assert hashlib.sha256(data).hexdigest() == mapping['p2_sha256']
text = data.decode()
start = text.index('func ' + mapping['function'] + '(')
end = text.index('\nfunc ', start + 1)
body = text[start:end]
assert hashlib.sha256(body.encode()).hexdigest() == mapping['body_sha256']
for anchor in mapping['checks']:
    assert body.count(anchor) == 1, anchor
print('PASS: 9 upstream identities, 14 source anchors, exact generated function; no runtime claim')
