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
(out / 'overlay.json').write_text(json.dumps({'Replace': replacements}, indent=2)+'\n')
(out / 'hashes.json').write_text(json.dumps(records, indent=2)+'\n')
