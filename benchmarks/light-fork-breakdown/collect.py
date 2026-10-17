"""Preserve all compact observations with original and normalized hashes."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(b):return hashlib.sha256(b).hexdigest()


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();out=a.output;out.mkdir(parents=True,exist_ok=False);ledger=[]
 for source in sorted((w/'evidence').rglob('*')):
  if not source.is_file():continue
  assert source.suffix in ['.json','.txt','.log'] and not source.is_symlink()
  rel=source.relative_to(w/'evidence');target=rel.with_suffix('.txt') if rel.suffix=='.log' else rel;b=source.read_bytes();s=b.decode()
  for old,new in [(str(w),'<WORKSPACE>'),(str(w.parents[2]),'<REPOSITORY>'),(str(Path.home())+'/', '<HOME>/')]:s=s.replace(old,new)
  final=s.endswith(('\n','\r'));s='\n'.join(line.rstrip() for line in s.splitlines())+('\n' if final else '');data=s.encode();dest=out/target;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(data);ledger.append(dict(source=str(rel),stored=str(target),original_sha256=digest(b),stored_sha256=digest(data)))
 (out/'preservation.json').write_text(json.dumps(ledger,indent=2)+'\n')
 for r in ledger:assert digest((out/r['stored']).read_bytes())==r['stored_sha256']
 print('PASS: all observation files and normalization hashes preserved')


if __name__=='__main__':main()
