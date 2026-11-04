"""Read-only replay of the exact, explicitly mapped nineteen-body ABI proof."""
from pathlib import Path
import sys,json,gzip,hashlib,re
p=Path(sys.argv[1]);v=json.loads(gzip.decompress(p.read_bytes()));mraw=(p.parent/'experimental-binding.json').read_bytes();assert hashlib.sha256(mraw).hexdigest()=='b82e9465c17933a2cdd783d4e146889c4f5d4816de713f18bea8ece9de1cfd23';manifest=json.loads(mraw)
assert hashlib.sha256(v['proof_json'].encode()).hexdigest()==manifest['proof_sha256'];proof=json.loads(v['proof_json'])
assert hashlib.sha256(v['baseline_fixture_json'].encode()).hexdigest()=='72d2a14eb58c6304bc4f4624ed801cd470c84595552b0ebe61e0b7e7f42ea1fc';fixture=json.loads(v['baseline_fixture_json'])
assert proof['result']=='PASS_EXACT_RELOCATION_ONLY' and proof['guest_sha256']==manifest['guest_sha256'];oc=proof['old_initializer'];nc=proof['new_initializer'];delta=proof['bss_delta'];assert delta==2754112 and nc['bss_bytes']==oc['bss_bytes']==8982576
assert nc['bss_start']-oc['bss_start']==nc['tls_start']-oc['tls_start']==nc['copies'][1][0]-oc['copies'][1][0]==delta
assert nc['copies'][0][0]==oc['copies'][0][0]==8388608 and nc['copies'][1][1]==oc['copies'][1][1]==642620
assert len(bytes.fromhex(v['tls']['baseline']))==505 and v['tls']['baseline']==v['tls']['candidate'];assert hashlib.sha256(bytes.fromhex(v['tls']['baseline'])).hexdigest()==fixture['tls_sha256']==manifest['tls_sha256'];assert v['globals']['baseline']==v['globals']['candidate'] and all(v['globals']['baseline'].values())
assert v['cstring']['baseline']==v['cstring']['candidate'] and v['cstring']['baseline_address']==8688301

def sha(text):return hashlib.sha256(re.sub(r'\s+','',text).encode()).hexdigest()
def tokens(text):return re.findall(r'0[xX][\da-fA-F]+|\d+|[A-Za-z_]\w*|[^\w\s]',text)
def number(x):return int(x,0) if re.fullmatch(r'0[xX][\da-fA-F]+|\d+',x) else None
def compare(before,after,constructor=False):
 before=re.sub(r'\bFn4068\b','Fn4069',before);a=tokens(before);b=tokens(after);assert len(a)==len(b)
 for left,right in zip(a,b):
  x=number(left);y=number(right);mutable=x is not None and (15244865<=x<=15471936 or (constructor and x in [oc['bss_start'],oc['bss_start']+oc['bss_bytes']]))
  if mutable:assert y is not None and y-x==delta
  elif constructor and x in [oc['copies'][1][0],oc['tls_start']]:assert y is not None and y-x==delta
  elif constructor and x==oc['copies'][0][1]:assert y==nc['copies'][0][1]
  elif x==8688301:assert y==v['cstring']['candidate_address']
  else:assert left==right,(left,right)
assert len(v['functions'])==len(fixture['functions'])==len(proof['functions'])==19
for bodies,old,new in zip(v['functions'],fixture['functions'],proof['functions']):
 assert sha(bodies['baseline'])==old['normalized_sha256'];assert sha(bodies['candidate'])==new['normalized_sha256'];compare(bodies['baseline'],bodies['candidate'])
compare(v['initializers']['baseline'],v['initializers']['candidate'],True)
def rejects(f):
 try:f()
 except AssertionError:return
 raise AssertionError('mutation admitted')
# Preserve the permitted address/name changes while rejecting semantic changes.
i=next(i for i,r in enumerate(proof['functions']) if r['function']=='Fn153');row=v['functions'][i];old,new=next(pair for pair in proof['functions'][i]['integer_changes'] if pair[0]!=pair[1]);bad=row['candidate'].replace(str(new),str(new+1),1);assert bad!=row['candidate'];rejects(lambda:compare(row['baseline'],bad))
i=next(i for i,r in enumerate(proof['functions']) if r['function']=='Fn213');row=v['functions'][i];bad=row['candidate'].replace('Fn4069','Fn4068');assert bad!=row['candidate'];rejects(lambda:compare(row['baseline'],bad));rejects(lambda:compare(row['baseline'],row['candidate']+'\nreturn 1\n'))
print('PASS readonly nineteen-body explicit relocation/call-map proof, TLS, globals, three semantic rejection controls')
