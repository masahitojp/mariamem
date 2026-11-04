"""Read-only startup observations; no guest/control-flow/configuration changes."""
import hashlib
import json
from pathlib import Path
import sys

root, out = (Path(v).resolve() for v in sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
replacements = {}
records = []

def patch(relative, edits):
    original = (root / relative).read_text()
    changed = original
    for before, after in edits:
        assert changed.count(before) == 1, (relative, before)
        changed = changed.replace(before, after)
    target = out / Path(relative).name
    target.write_text(changed)
    replacements[str(root / relative)] = str(target)
    records.append({'path': relative, 'before_sha256': hashlib.sha256(original.encode()).hexdigest(),
                    'after_sha256': hashlib.sha256(changed.encode()).hexdigest()})

patch('internal/timing/timing.go', [
    ('var sequence atomic.Uint64', '''// Experimental observer: one host monotonic clock, installed before any startup.
var ForkObserver func(string, time.Time)
func ForkStageMark(name string) {
    if ForkObserver != nil { ForkObserver("runtime/"+name, time.Now()) }
}
var sequence atomic.Uint64'''),
    ('if t, ok := ctx.Value(key{}).(*Trace); ok && !at.IsZero() {',
     'if t, ok := ctx.Value(key{}).(*Trace); ok && !at.IsZero() {\n        if ForkObserver != nil { ForkObserver(t.Operation+"/"+name, at) }')])
patch('internal/generatedgo/runtime_instance.go', [
    ('"io"', '"io"\n"os"'),
    ('values = append(values, "MARIAMEM_GUEST_TIMING=1")', 'values = append(values, "MARIAMEM_GUEST_TIMING=1")\n        if os.Getenv("MARIAMEM_PROBE_INIT") == "1" { values = append(values, "MARIAMEM_INIT_DIAGNOSTICS=1") }'),
    ('"github.com/masahitojp/mariamem/internal/prepared"', '"github.com/masahitojp/mariamem/internal/prepared"\n"github.com/masahitojp/mariamem/internal/timing"'),
    ('var libraryMode sync.Once', 'var libraryMode sync.Once\n// Experimental read handle; invoked only after Fork returns and before child Close.\nvar ForkGuestTimingReader func(func() ([]byte, error))'),
    ('go func() {\n\t\tvar err error', 'go func() {\n        timing.ForkStageMark("instance_begin")\n\t\tvar err error'),
    ('\t\tw := base.DefaultWASI()', '\t\tw := base.DefaultWASI()\n        timing.ForkStageMark("filesystem_begin")'),
    ('\t\tvar maps *base.PreparedFiles', '''        timing.ForkStageMark("filesystem_environment_ready")
        if ForkGuestTimingReader != nil && guestTiming {
            ForkGuestTimingReader(func() ([]byte, error) {
                f, e := fs.OpenFile("snapshot-out/startup-timing.json", 0, 0)
                if e != nil { return nil, e }; defer f.Close()
                return io.ReadAll(io.LimitReader(f, 128*1024+1))
            })
        }
\t\tvar maps *base.PreparedFiles'''),
    ('\t\tif restore != nil {\n\t\t\tmaps, err', '\t\tif restore != nil {\n            timing.ForkStageMark("prepared_handles_begin")\n\t\t\tmaps, err'),
    ('\t\th := &host{', '        timing.ForkStageMark("prepared_handles_ready")\n\t\th := &host{'),
    ('\t\tif err = executeGuest(m, generated.Start);', '        timing.ForkStageMark("guest_execute_begin")\n\t\tif err = executeGuest(m, generated.Start);')])
patch('internal/generatedgo/memory_backing_unix.go', [
    ('"fmt"', '"fmt"\n"github.com/masahitojp/mariamem/internal/timing"'),
    ('\tb, err := reserve()', '\ttiming.ForkStageMark("reserve_begin")\n\tb, err := reserve()\n    timing.ForkStageMark("reserve_end")'),
    ('\tm = initialize(b)', '\ttiming.ForkStageMark("construct_begin")\n\tm = initialize(b)\n    timing.ForkStageMark("construct_end")')])
# Exact generated function identified from the static data addresses for
# embedded_begin/options_complete, plus ordered my_timer_init field accesses.
relative='internal/generatedgo/code/p0/p0_pure.go'
original=(root/relative).read_text()
start=original.index('func Fn5572('); end=original.index('\nfunc ',start+1)
body=original[start:end]
edits=[
 ('\tFn227(m, int32(8563877))','\tcommonInitMark("common_begin")\n\tFn227(m, int32(8563877))'),
 ('L64:\n\t;\n\tv735 = int32(0)','L64:\n\t;\n\tcommonInitMark("timer_begin")\n\tv735 = int32(0)'),
 ('L1466:\n\t;\n\tm.G0 = v739 + int32(32)','L1466:\n\t;\n\tm.G0 = v739 + int32(32)\n\tcommonInitMark("timer_end_common_variables_begin")'),
 ('L1826:\n\t;','L1826:\n\t;\n\tcommonInitMark("common_variables_end")'),
 ('\tFn227(m, int32(8620041))','\tcommonInitMark("common_end")\n\tFn227(m, int32(8620041))')]
edits += [
 ('\tv11639 = Fn15260(m, int32(23886496))','\tcommonInitMark("status_begin")\n\tv11639 = Fn15260(m, int32(23886496))'),
 ('L2004:\n\t;','L2004:\n\t;\n\tcommonInitMark("options_begin")'),
 ('L2487:\n\t;','L2487:\n\t;\n\tcommonInitMark("options_version_uid_end")'),
 ('L2675:\n\t;','L2675:\n\t;\n\tcommonInitMark("error_messages_begin")'),
 ('\tFn5810(m)','\tcommonInitMark("sql_registration_begin")\n\tFn5810(m)'),
 ('L2833:\n\t;','L2833:\n\t;\n\tcommonInitMark("charset_begin")'),
]
edits += [('\tv16221 = Fn969(m, v16218, int32(32), v16140)', '\tcommonInitMark("default_lookup_begin")\n\tv16221 = Fn969(m, v16218, int32(32), v16140)\n\tcommonInitMark("default_lookup_end")'), ('L2933:\n\t;', 'L2933:\n\t;\n\tcommonInitMark("charset_log_defaults_end")'), ('\tv16584 = Fn21527(m, int32(23877496), int32(23876648), v62+int32(368))', '\tcommonInitMark("path_parse_begin")\n\tv16584 = Fn21527(m, int32(23877496), int32(23876648), v62+int32(368))\n\tcommonInitMark("path_parse_end")'), ('L2943:\n\t;', 'L2943:\n\t;\n\tcommonInitMark("db_cache_begin")'), ('L2956:\n\t;', 'L2956:\n\t;\n\tcommonInitMark("case_probe_begin")'), ('L2964:\n\t;\n\tm.G0 = v16765 + int32(1184)', 'L2964:\n\t;\n\tm.G0 = v16765 + int32(1184)\n\tcommonInitMark("case_probe_end")')]
edits += [('\tv16119 = Fn20110(m, int32(23877424), v62+int32(368), v16107)','\tcommonInitMark("collation_parse_begin")\n\tv16119 = Fn20110(m, int32(23877424), v62+int32(368), v16107)\n\tcommonInitMark("collation_parse_end")')]
for before,after in edits:
 assert body.count(before)==1,(relative,before)
 body=body.replace(before,after)
changed=original[:start]+body+original[end:]
changed=changed.replace('"sync/atomic"','"sync/atomic"\n"os"\n"github.com/masahitojp/mariamem/internal/timing"',1)
changed += '\nvar commonInitEnabled = os.Getenv("MARIAMEM_PROBE_COMMON") == "1"\nfunc commonInitMark(name string) { if commonInitEnabled { timing.ForkStageMark("commoninit/"+name) } }\n'
target=out/'common-p0.go';target.write_text(changed)
replacements[str(root/relative)]=str(target)
records.append({'path':relative,'function':'Fn5572','before_sha256':hashlib.sha256(original.encode()).hexdigest(),'after_sha256':hashlib.sha256(changed.encode()).hexdigest(),'edits':edits})
# Once-initializer selected by Fn820's table slot542 -> Fn960.
# The entry/defer callback observes every actual initializer invocation; root
# setup is outside the active child collector, never relabelled as child work.
relative='internal/generatedgo/code/p1/p1_pure.go'
original=(root/relative).read_text()
needle='func Fn960(m *base.Module) {'
assert original.count(needle)==1
changed=original.replace(needle,needle+'\n charsetInitMark("registry_begin")\n defer charsetInitMark("registry_end")',1)
changed=changed.replace('"sync/atomic"','"sync/atomic"\n"os"\n"github.com/masahitojp/mariamem/internal/timing"',1)
changed += '\nvar charsetInitEnabled = os.Getenv("MARIAMEM_PROBE_COMMON") == "1"\nfunc charsetInitMark(name string) { if charsetInitEnabled { timing.ForkStageMark("commoninit/"+name) } }\n'
target=out/'charset-p1.go';target.write_text(changed)
replacements[str(root/relative)]=str(target)
records.append({'path':relative,'function':'Fn960','before_sha256':hashlib.sha256(original.encode()).hexdigest(),'after_sha256':hashlib.sha256(changed.encode()).hexdigest(),'entry_and_defer':'registry begin/end; selected by table slot542 in charsets once gate Fn820'})
(out / 'overlay.json').write_text(json.dumps({'Replace': replacements}, indent=2)+'\n')
(out / 'hashes.json').write_text(json.dumps(records, indent=2)+'\n')
