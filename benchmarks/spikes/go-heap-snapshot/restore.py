"""Restore only overlay outputs whose recorded postimages still match."""
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE='a8137b8b444f86068d3128a291e3a848adfdfd56'
changes=json.loads((HERE/'instrumentation.json').read_text())
for name,item in changes.items():
 p=ROOT/name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==item['after'],name
for name,item in changes.items():
 p=ROOT/name
 if item['before'] is None:p.unlink()
 else:
  original=subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT)
  assert hashlib.sha256(original).hexdigest()==item['before'],name
  p.write_bytes(original)
