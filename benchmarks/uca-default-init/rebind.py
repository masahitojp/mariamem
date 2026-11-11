from pathlib import Path
import re,subprocess,hashlib,json,difflib
refs={'prior':'b0c457e1d314b8a957ff7b149d400be4ae05a146','current':'500020e7dc6d702ef059f0e73a4bab738103b774'}
def source(ref,path):return subprocess.check_output(['git','show',ref+':'+path],text=True)
def helpers(ref):
 s=source(ref,'internal/generatedgo/code/base/base.go');out={}
 for m in re.finditer(r'^func (Simd_p_fx\d+)\(',s,re.M):
  body=s[m.start():s.index('\n}',m.end())+2];out[m[1]]=hashlib.sha256(body.replace(m[1],'HELPER',1).encode()).hexdigest()
 return out
h={k:helpers(v) for k,v in refs.items()};results=[]
for n in [465,468,610]:
 texts={}
 for arm,ref in refs.items():
  path='internal/generatedgo/code/'+('p3/p3_pure.go' if n==610 else 'p2/p2_pure.go');s=source(ref,path);m=re.search(r'^func Fn'+str(n)+r'\(',s,re.M);body=s[m.start():s.index('\n}',m.end())+2]
  norm=re.sub(r'base\.(Simd_p_fx\d+)',lambda m:'base.HELPER_'+h[arm][m[1]],body);texts[arm]=(body,norm)
 equal=texts['prior'][1]==texts['current'][1];assert equal, ''.join(difflib.unified_diff(texts['prior'][1].splitlines(True),texts['current'][1].splitlines(True)))[:1500]
 results.append({'function':n,'literal_body_equal':texts['prior'][0]==texts['current'][0],'verified_helper_body_normalized_equal':equal,'prior_body_sha256':hashlib.sha256(texts['prior'][0].encode()).hexdigest(),'current_body_sha256':hashlib.sha256(texts['current'][0].encode()).hexdigest()})
Path('../evidence/rebind-proof.json').write_text(json.dumps({'sources':refs,'method':'Full bodies compared after replacing helper call names with hashes of their complete definition, normalizing only each helper declaration name. No other substitutions.','functions':results},indent=2)+'\n');print('Full-body helper-identity rebind PASS',len(results))
