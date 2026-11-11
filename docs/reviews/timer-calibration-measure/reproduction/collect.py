from pathlib import Path
import json,hashlib
W=Path(__file__).resolve().parents[1];E=W/'evidence';B=W.parent/'timer-measure-baseline'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((E/'run.json').read_text());jobs=json.loads((E/'jobs.json').read_text())['jobs'];arts=json.loads((E/'artifacts.json').read_text())['artifacts']
ci={'run':{k:r[k] for k in ('id','head_sha','event','status','conclusion','run_attempt','html_url')},'jobs':[{k:j[k] for k in ('id','name','conclusion','html_url')} for j in jobs],'artifacts':[{k:a[k] for k in ('id','name','digest','size_in_bytes')} for a in arts]}
for a in ci['artifacts']:
 filename='guest.zip' if a['id']==13814809081 else 'ci-evidence.zip';assert 'sha256:'+sha(W/'temp'/filename)==a['digest'];a['archive_digest_verified']=True
ci['assessment']=json.loads((W/'temp/ci-evidence/assessment.json').read_text());ci['original_assessment_sha256']=sha(W/'temp/ci-evidence/assessment.json')
(E/'ci-receipt.json').write_text(json.dumps(ci,indent=2)+'\n')
for arm,A in [('baseline',B),('candidate',W)]:
 d=json.loads((A/'temp/runtime/development.json').read_text())
 compact={k:d[k] for k in ('contract','result','smoke','guest_sha256','guest_record_sha256','binary_sha256','binary_bytes','installation_inputs_sha256')}
 compact.update(guest_source_commit=d['source_identity']['commit'],host_source_commit=d['host_source_identity']['commit'],development_record_sha256=sha(A/'temp/runtime/development.json'))
 compact['generated_inventory_sha256']=hashlib.sha256(json.dumps(d['generated_inventory'],sort_keys=True).encode()).hexdigest()
 compact['go_buildinfo']=d['go_buildinfo'].replace(str(A),'<WORKSPACE>')
 compact['raw_translation_identity']={k:d['raw_translation'][k] for k in ('guest_sha256','converter_commit','converter_archive_sha256','patched_converter_sha256','patches_sha256')}
 (E/(arm+'-host.json')).write_text(json.dumps(compact,indent=2)+'\n')
print('CI and both host receipts reduced')
