#!/usr/bin/env python3
"""Assess exact product/spike composition on selected pinned source files only."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request

repo=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(repo/'scripts'))
from guest_input import descriptor,apply_series
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();temp=w/'temp';e=w/'evidence';temp.mkdir(exist_ok=True);e.mkdir(exist_ok=True)
lock=json.loads((repo/'release/inputs.lock.json').read_text());desc=descriptor(repo,lock)
patches=[repo/v['file'] for v in desc['patches']]+[repo/'guest/source.patch',repo/'guest/experimental.patch']
files=set(desc['recipe_files_sha256'])
for patch in patches:files.update(re.findall(r'^\+\+\+ b/(.+)$',patch.read_text(),re.M))
files.update(['libmysqld/CMakeLists.txt','sql/CMakeLists.txt','vio/vio.c','vio/viosocket.c'])
pristine=temp/'pristine';pristine.mkdir()
archives={}
for name in ['mariadb','lite4mariadb']:
 pin=next(x for x in lock['inputs'] if x['name']==name);archive=temp/pin['file']
 if not archive.exists():
  with urllib.request.urlopen(pin['url'],timeout=90) as src,archive.open('wb') as out:shutil.copyfileobj(src,out)
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==pin['sha256'];archives[name]={'source_commit':pin['revision'],'sha256':pin['sha256']}
 with tarfile.open(archive) as tar:
  for member in tar.getmembers():
   rel=member.name.split('/',1)[-1]
   selected=rel in files if name=='mariadb' else rel in desc['recipe_files_sha256']
   if member.isfile() and selected:
    data=tar.extractfile(member).read()
    if name=='lite4mariadb':assert hashlib.sha256(data).hexdigest()==desc['recipe_files_sha256'][rel]
    out=pristine/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
product=temp/'product';shutil.copytree(pristine,product)
with (e/'product-overlays.txt').open('w') as log:
 # apply_series checks exact before and after hashes; retain its stdout too.
 import contextlib
 with contextlib.redirect_stdout(log):apply_series(repo,product,desc)
 subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-i',str(repo/'guest/source.patch')],cwd=product,stdout=log,stderr=subprocess.STDOUT,check=True)
with (e/'stack-dry-run.txt').open('w') as log:
 result=subprocess.run(['patch','--dry-run','--batch','--forward','--fuzz=0','-p1','-i',str(repo/'guest/experimental.patch')],cwd=product,stdout=log,stderr=subprocess.STDOUT)
native=temp/'native';shutil.copytree(pristine,native)
with (e/'native-overlay.txt').open('w') as log:subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-i',str(repo/'guest/experimental.patch')],cwd=native,stdout=log,stderr=subprocess.STDOUT,check=True)
names=re.findall(r'^\+\+\+ b/(.+)$',(repo/'guest/experimental.patch').read_text(),re.M)
composition={};delta=[]
for name in names:
 b=pristine/name;x=product/name;y=native/name;base=b.read_bytes() if b.exists() else b'';left=x.read_bytes() if x.exists() else b'';right=y.read_bytes()
 if left==base:merged=right;status=0
 else:
  r=subprocess.run(['git','merge-file','-p',str(x),str(b),str(y)],stdout=subprocess.PIPE,stderr=subprocess.PIPE);status=r.returncode;merged=r.stdout
 composition[name]={'product_changed':left!=base,'three_way_conflicts':status,'product_sha256':hashlib.sha256(left).hexdigest() if left else None,'spike_sha256':hashlib.sha256(right).hexdigest()}
 if status:
  # Both observed conflicts append different helpers at EOF. Preserve both;
  # assert the native fragment so no unrelated conflict is silently resolved.
  conflict=merged.decode().replace(str(x),'PRODUCT').replace(str(b),'UPSTREAM').replace(str(y),'NATIVE3B')
  chunks=list(re.finditer(r'^<<<<<<< PRODUCT\n(.*?)^=======\n(.*?)^>>>>>>> NATIVE3B\n',conflict,re.M|re.S))
  expected={'libmysqld/lib_sql.cc':'#include "mariamem_wire_probe.inc"','sql/sql_prepare.cc':'unsigned long mariamem_spike_decodes= 0;'}
  assert len(chunks)==1 and chunks[0][2].strip()==expected[name],name
  assert 'mariamem_stmt_parameter_' in chunks[0][1],name
  out=e/'conflicts'/(name+'.json');out.parent.mkdir(parents=True,exist_ok=True)
  out.write_text(json.dumps({'file':name,'original_conflict_excerpt':chunks[0][0]},indent=2)+'\n')
  merged=(conflict[:chunks[0].start()]+chunks[0][1]+chunks[0][2]+conflict[chunks[0].end():]).encode()
  composition[name]['draft_resolution']='retain product metadata helper and append exact independent3B declaration/include'
 if status==0 or 'draft_resolution' in composition[name]:
  composition[name]['composed_sha256']=hashlib.sha256(merged).hexdigest()
  delta.extend(difflib.unified_diff(left.decode().splitlines(True),merged.decode().splitlines(True),fromfile='a/'+name if left else '/dev/null',tofile='b/'+name))
report={'scope':'selected-source overlay assessment; no full source preparation or engine build','archives':archives,'patches':{str(x.relative_to(repo)):hashlib.sha256(x.read_bytes()).hexdigest() for x in patches},'direct_stack_exit_code':result.returncode,'files':composition,'all_three_way_clean':all(not x['three_way_conflicts'] for x in composition.values())}
report['draft_resolved_all']=all(not x['three_way_conflicts'] or 'draft_resolution' in x for x in composition.values())
(e/'overlay.json').write_text(json.dumps(report,indent=2)+'\n')
if report['draft_resolved_all']:
 (e/'composed-draft.patch').write_text(''.join(delta))
 composed=temp/'composed';shutil.copytree(product,composed)
 with (e/'composed-apply.txt').open('w') as log:
  subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-i',str(e/'composed-draft.patch')],cwd=composed,stdout=log,stderr=subprocess.STDOUT,check=True)
 for name,pin in composition.items():assert hashlib.sha256((composed/name).read_bytes()).hexdigest()==pin['composed_sha256'],name
 for name,anchor in [('libmysqld/lib_sql.cc','#ifdef __wasi__\nextern "C" void *mariamem_stmt_parameter_items'),('sql/sql_prepare.cc','#if defined(EMBEDDED_LIBRARY) && defined(__wasi__)\n/* Public C API adapter')]:
  original=(product/name).read_text();assert original[original.index(anchor):] in (composed/name).read_text(),name
 prepared=(composed/'sql/sql_prepare.cc').read_text()
 assert 'set_time(&tm, MYSQL_TIMESTAMP_TIME, MAX_TIME_FULL_WIDTH);' in prepared
 assert prepared.count('param->unsigned_flag= client_param->is_unsigned;')>=2
 untouched=[]
 for original in product.rglob('*'):
  name=str(original.relative_to(product))
  if original.is_file() and name not in composition:
   assert original.read_bytes()==(composed/name).read_bytes(),name;untouched.append(name)
 (e/'composition-verification.json').write_text(json.dumps({'patch_apply_exit_code':0,'all14_composed_file_hashes_match':True,'product_metadata_helper_blocks_preserved_exactly':True,'TIME_width_and_unsigned_bind_corrections_present':True,'other_product_selected_files_unchanged':sorted(untouched),'status':'uncompiled draft; no semantic/runtime acceptance'},indent=2)+'\n')
print(json.dumps({'direct_stack_exit_code':result.returncode,'all_three_way_clean':report['all_three_way_clean'],'overlapping_files':[k for k,v in composition.items() if v['product_changed']],'conflicting_files':[k for k,v in composition.items() if v['three_way_conflicts']]},indent=2))
