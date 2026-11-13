from pathlib import Path
import json,importlib.util
r=Path(__file__).resolve().parents[1];e=r/'evidence';spec=importlib.util.spec_from_file_location('analysis',e/'analyze.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
record=next(x for x in json.loads((e/'runs.json').read_text()) if x['name']=='primary-p8-full-0');raw=m.load_event(e/(record['name']+'-events.json'));out=[]
for kind in ['missing_response_boundary','noncausal_clock','wrong_label']:
 d=json.loads(json.dumps(raw));c=next(x for x in d['clients'] if x['Stage']=='item');l=next(x for x in d['ledgers'] if x['label']==c['Label']);q=next(x for x in l['requests'].values() if x['HostWriteStart']>=c['Start'] and 0<x['HostReadEnd']<=c['End'])
 if kind=='missing_response_boundary':q['HostReadEnd']=0
 elif kind=='noncausal_clock':q['GuestWriteStart']=q['GuestReadEnd']-1
 else:c['Label']='wrong-label'
 directory=r/'temp/negative'/kind;directory.mkdir(parents=True,exist_ok=True);(directory/(record['name']+'-events.json')).write_text(json.dumps(d));m.r=directory
 try:m.process(record)
 except (AssertionError,KeyError):out.append({'control':kind,'rejected':True})
 else:raise AssertionError('bad observation accepted: '+kind)
(e/'negative-controls.json').write_text(json.dumps(out,indent=2));print('PASS: all3 label/boundary/clock corruptions rejected')
