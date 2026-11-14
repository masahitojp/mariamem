from pathlib import Path
import subprocess,re,json,gzip
W=Path(__file__).resolve().parents[1];E=W/'evidence';T=W/'temp';out={}
pattern='code/p[0-8]\\.Fn(68|15594|14146|13338|15541|17041|13977|13460)$'
for label in ['baseline','candidate']:
 s=subprocess.check_output(['go','tool','objdump','-s',pattern,str(T/(label+'.test'))],text=True)
 (E/(label+'-selected-assembly.txt.gz')).write_bytes(gzip.compress(s.encode(),mtime=0));functions={};current=None
 for line in s.splitlines():
  if line.startswith('TEXT '):current=line.split()[1];functions[current]={'instructions':0,'memory_ea_calls':0}
  elif current and line.strip():
   functions[current]['instructions']+=1
   if 'CALL 'in line and 'base.MemoryEA' in line:functions[current]['memory_ea_calls']+=1
 out[label]=functions
(E/'mechanism.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
