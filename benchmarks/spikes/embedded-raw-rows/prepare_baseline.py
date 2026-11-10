"""Extract exact existing serializers; no alternative oracle implementation."""
import hashlib,json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[3]
out=pathlib.Path(sys.argv[1]);recipe=pathlib.Path(sys.argv[2]).read_bytes()
assert hashlib.sha256(recipe).hexdigest()=='c0a959b6755d3463de31d9d08d2a43031cc418a332768a0956ebfd5046e15526'
s=recipe.decode();a=s[s.index('typedef struct'):s.index('static char *dup_str')]
s=(root/'guest/wire_core.inc').read_text();b=s[s.index('static int wire_state'):s.index('EMSCRIPTEN_KEEPALIVE')]
s=(root/'guest/prepared_api.inc').read_text();c=s[:s.index('static char *ps_capture_result')]
out.write_text(a+'\n'+b+'\n'+c)
print(json.dumps({'baseline_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['guest/wire_core.inc','guest/prepared_api.inc']}}))
