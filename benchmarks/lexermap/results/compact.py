import json
def pack(observations):
 templates=[];ids={};maps={};processes={}
 for name,report in observations.items():
  r=dict(report);samples=[]
  for s in report['Samples']:
   v=dict(s);seq=[];elapsed=[]
   for row in s['Rows'] or []:
    template=dict(row);elapsed.append(template.pop('elapsed_ns'))
    if 'pair_hex' in template:maps[template['pair_sha256']]=template.pop('pair_hex')
    key=json.dumps(template,sort_keys=True)
    if key not in ids:ids[key]=len(templates);templates.append(template)
    seq.append(ids[key])
   v['Rows']=None if s['Rows'] is None else {'templates':seq,'elapsed_ns':elapsed}
   samples.append(v)
  r['Samples']=samples;processes[name]=r
 return {'format':1,'templates':templates,'maps':maps,'processes':processes}
def unpack(p):
 assert p['format']==1
 observations={}
 for name,report in p['processes'].items():
  r=dict(report);samples=[]
  for s in report['Samples']:
   v=dict(s);rows=[]
   if s['Rows'] is not None:
    assert len(s['Rows']['templates'])==len(s['Rows']['elapsed_ns'])
    for idx,ns in zip(s['Rows']['templates'],s['Rows']['elapsed_ns']):
     row=dict(p['templates'][idx],elapsed_ns=ns)
     if 'pair_sha256' in row:row['pair_hex']=p['maps'][row['pair_sha256']]
     rows.append(row)
   v['Rows']=None if s['Rows'] is None else rows;samples.append(v)
  r['Samples']=samples;observations[name]=r
 return observations
