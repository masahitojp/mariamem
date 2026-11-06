"""Lossless encoding of the fields consumed by the numerical reducer."""
import copy,json

def pack(records):
 data=copy.deepcopy(records);names=[]
 for r in data:
  for t in r.get('traces',{}).values():
   init=t['startup']['guest']['initialization'];packed=[]
   for e in init['events']:
    assert set(e)=={'name','offset_ns','process_cpu_ns','thread_cpu_ns'}
    assert e['process_cpu_ns'] is None and e['thread_cpu_ns'] is None
    if e['name'] not in names:names.append(e['name'])
    packed.append([names.index(e['name']),e['offset_ns']])
   init['events']=packed;init['cpu_unavailable']=True
 return {'encoding':'init-name-index-and-offset-v1','event_names':names,'records':data}

def unpack(data):
 assert data['encoding']=='init-name-index-and-offset-v1'
 names=data['event_names'];assert len(names)==len(set(names));rs=copy.deepcopy(data['records'])
 for r in rs:
  for t in r.get('traces',{}).values():
   init=t['startup']['guest']['initialization'];assert init.pop('cpu_unavailable') is True
   init['events']=[{'name':names[i],'offset_ns':ns,'process_cpu_ns':None,'thread_cpu_ns':None} for i,ns in init['events']]
 return rs

def read(root):return unpack(json.loads((root/'observations.json').read_text()))
