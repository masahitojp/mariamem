import sys,json,time
from pathlib import Path
sys.path.insert(0,'/exp/worktree/scripts')
from build_generated_guest import download
from common import ROOT,fetch,LOCK
from guest_input import descriptor
for key,pin in json.loads((ROOT/'release/generated-go-toolchain.json').read_text())['archives'].items():
 for attempt in range(3):
  try:download(pin,ROOT/'build/downloads');print(key,flush=True);break
  except Exception:
   if attempt==2:raise
for name in [descriptor(ROOT,LOCK)['source_input'],'lite4mariadb','libmariadb','wolfssl','pcre2','libfmt']:
 fetch(name);print(name,flush=True)
