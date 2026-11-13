from pathlib import Path
import json,urllib.request,hashlib
E=Path(__file__).resolve().parent;rs=json.loads((E/'source-files.json').read_text());commit='09503b230e8acc721c1e013ca28a41bf149e4ee2'
for r in rs:
 if '/wasix-org/wasix-libc/' in r['url']:
  u=r['url'].replace('v2026-07-03.1',commit);b=urllib.request.urlopen(u,timeout=30).read();assert hashlib.sha256(b).hexdigest()==r['sha256'];r['url']=u
(E/'source-files.json').write_text(json.dumps(rs,indent=2)+'\n');(E/'libc-identity.json').write_text(json.dumps({'tag':'v2026-07-03.1','source_commit':commit,'object_type':'commit','method':'GitHub git/ref plus byte-identical refetch of selected source files at commit'},indent=2)+'\n')
