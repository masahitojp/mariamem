"""Assemble the experimental patch from checked source-oracle outputs."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
from failure_fix import apply as fix_failure

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--check-output',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[2]
here=Path(__file__).resolve().parent
src=a.source.resolve();check=a.check_output.resolve()
pins=json.loads((here/'inputs.json').read_text())
sha=lambda b:hashlib.sha256(b).hexdigest()
original=(src/'ctype-uca.c').read_text()
assert sha(original.encode())==pins['sha256']['ctype-uca.c']
record=json.loads((check/'result.json').read_text())
assert record['result']=='PASS_SOURCE_ONLY'
for name, digest in record['implementation_sha256'].items():
    assert sha((here/name).read_bytes())==digest, 'untested implementation: '+name
header=(check/'prepared.h').read_text()
assert sha(header.encode())==record['prepared_header_sha256']
canonical=(root/'guest/source.patch').read_text()
start=canonical.index('--- a/strings/ctype-uca.c\n')
end=canonical.find('\n--- a/',start+1)
assert end!=-1
subset=canonical[start:end]+'\n'
prepared=check/'canonical';(prepared/'strings').mkdir(parents=True,exist_ok=True)
(prepared/'strings/mariamem_uca_copy_prepared.h').unlink(missing_ok=True)
(prepared/'strings/ctype-uca.c').write_text(original)
subprocess.run(['patch','--batch','--fuzz=0','-p1'],input=subset,text=True,cwd=prepared,check=True,capture_output=True)
before=(prepared/'strings/ctype-uca.c').read_text()
helper=(here/'copy.c').read_text()
anchor='static my_bool\ninit_weight_level('
assert before.count(anchor)==1
insert='#if defined(__wasi__)\n#include "mariamem_uca_copy_prepared.h"\n'+helper+'#endif\n\n'
after=fix_failure(before.replace(anchor,insert+anchor))
anchor='''  if ((my_uca_generate_pages(loader, dst, rules->uca, src, (uint)npages)))
    return TRUE;
'''
assert after.count(anchor)==1
after=after.replace(anchor,anchor+'''
#if defined(__wasi__)
  {
    int copied= mariamem_uca_copy_default(loader, cs, rules, dst, src);
    if (copied < 0)
      return TRUE;
    if (copied > 0)
      goto mariamem_uca_copy_ready;
  }
#endif
''')
anchor='  if (cs->mbminlen == 1)\n    dst->booster= my_uca_level_booster_new(loader, cs, dst);'
assert after.count(anchor)==1
after=after.replace(anchor,'#if defined(__wasi__)\nmariamem_uca_copy_ready:\n#endif\n'+anchor)
patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/strings/ctype-uca.c',tofile='b/strings/ctype-uca.c',n=0))
patch+=''.join(difflib.unified_diff([],header.splitlines(True),fromfile='/dev/null',tofile='b/strings/mariamem_uca_copy_prepared.h'))
a.output.write_text(patch)
subprocess.run(['patch','--dry-run','--batch','--fuzz=0','-p1'],input=patch,text=True,cwd=prepared,check=True,capture_output=True)
subprocess.run(['patch','--batch','--fuzz=0','-p1'],input=patch,text=True,cwd=prepared,check=True,capture_output=True)
assert (prepared/'strings/ctype-uca.c').read_text()==after
assert (prepared/'strings/mariamem_uca_copy_prepared.h').read_text()==header
print(json.dumps({'result':'PATCH_APPLIES_AFTER_CANONICAL_UCA','experimental_patch_sha256':sha(patch.encode()),'canonical_source_patch_sha256':sha(canonical.encode()),'prepared_ctype_uca_sha256':sha(after.encode()),'header_sha256':sha(header.encode()),'patch_bytes':len(patch.encode()),'new_guest_execution':False},indent=2))
