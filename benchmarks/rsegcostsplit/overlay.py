from pathlib import Path
import hashlib
import json
import runpy
import sys

s, o = map(lambda p: Path(p).resolve(), sys.argv[1:])
d = s / 'benchmarks/rsegcostsplit'
runpy.run_path(str(s / 'benchmarks/trxstartupsplit/overlay.py'), run_name='__main__')
mapping = json.loads((o / 'overlay.json').read_text())
hashes = json.loads((o / 'hashes.json').read_text())
layout = json.loads((s / 'docs/reviews/rseg-source-check/generated-mapping.json').read_text())
p = s / 'internal/generatedgo/code/p2/p2_pure.go'
assert hashlib.sha256(p.read_bytes()).hexdigest() == layout['p2_sha256']
before = Path(mapping['Replace'][str(p)]).read_text()
a = before.index('func Fn17233(')
z = before.index('\nfunc ', a + 1)
original = before[a:z]
assert hashlib.sha256(original.encode()).hexdigest() == layout['body_sha256']
body = original
def patch(old, new):
    global body
    assert body.count(old) == 1, old
    body = body.replace(old, new)

patch('func Fn17233(m *base.Module) int32 {', 'func Fn17233(m *base.Module) int32 {\n rc := base.RsegCostBegin(m)\n defer rc.Finish()')
calls = [
    'Fn18164(m, int64(5), int32(2), v115, int32(10), v33, v115)',
    'Fn18164(m, v324<<(uint(int64(32))%64), int32(2), int32(0), int32(10), v33, v21+int32(740))',
    'Fn18164(m, v341|v343<<(uint(int64(32))%64), int32(2), int32(0), int32(10), v33, v21+int32(740))',
    'Fn18164(m, base.I64_extend_i32_u(v729)|v738<<(uint(int64(32))%64), int32(1), int32(0), int32(10), v33, v21+int32(740))',
]
for kind, call in enumerate(calls):
    patch(call, 'func()int32{defer rc.Page(' + str(kind) + ')(); return ' + call + '}()')
call = 'Fn16802(m, v258, v593, int32(base.Ui32((v616^base.I32_rotr(v616, int32(16)))&int32(-16711936))>>(uint(v624)%32))^base.I32_rotr(v616, v624))'
patch(call, 'func()int32{defer rc.Undo()(); return ' + call + '}()')
patch('v258 = v256 + int32(17881280)', 'v258 = v256 + int32(17881280)\n rc.Register()')
q = 'v588 = *(*int32)(unsafe.Add(mBase, base.MemoryEA(m, 26850608, 0, 4)))'
patch(q, q + '\n rc.ScanBegin(v588)')
patch('\nL84:\n\t;', '\nL84:\n\t;\n rc.ScanEnd()')
after = before[:a] + body + before[z:]
out = o / 'rsegcost-p2.go'
out.write_text(after)
mapping['Replace'][str(p)] = str(out)
hashes.append(dict(path=str(p.relative_to(s)), before_sha256=hashlib.sha256(before.encode()).hexdigest(), after_sha256=hashlib.sha256(after.encode()).hexdigest()))
for src, dst in [('span.go.txt', 'rseg_cost.go'), ('span-test.go.txt', 'rseg_cost_test.go')]:
    target = s / 'internal/generatedgo/code/base' / dst
    inp = d / src
    mapping['Replace'][str(target)] = str(inp)
    hashes.append(dict(path=str(target.relative_to(s)), before_sha256=None, after_sha256=hashlib.sha256(inp.read_bytes()).hexdigest()))
(o / 'overlay.json').write_text(json.dumps(mapping, indent=2) + '\n')
(o / 'hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
(o / 'rseg-mapping.json').write_text(json.dumps(dict(function='Fn17233', body_sha256=layout['body_sha256'], page_categories=['trx_sys', 'space_header', 'rseg_header', 'history_page'], page_calls=calls, undo_call=call, scan_begin='after v588 page size load before L82/L85', scan_end='L84 after completed loop; nested undo time subtracted', counter='page_size/16 per completed scan, undo_calls counts non-null slots; no per-slot hook'), indent=2) + '\n')
