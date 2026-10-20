"""Post-exit timing export for a diagnostic binary, not candidate source.

Only the HANDWRITTEN_FILES-owned execution adapter is overlaid by Go's compiler.
No generated file is edited; the candidate's complete inventory stays intact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OWNER = 'internal/generatedgo/runtime_instance.go'
EXPECTED = '8166f027fb23c9117c3eca08d767dce24f7bbd36b3f6ac81cc829cc223c1c796'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT/'scripts'))
    from generate_runtime import HANDWRITTEN_FILES
    assert OWNER.removeprefix('internal/generatedgo/') in HANDWRITTEN_FILES
    source = (ROOT/OWNER).read_bytes()
    target = args.product.resolve()/OWNER
    assert hashlib.sha256(source).hexdigest() == EXPECTED
    assert target.read_bytes() == source
    text = source.decode()
    anchor = '\t\tif len(captures) > 0 && captures[0] != nil && captures[0].Requested() {\n'
    assert text.count(anchor) == 1 and text.count('\t"io"\n') == 1
    observe = '''
        // DIAGNOSTIC ONLY. All guest startup/work has ended before this copy.
        // ExportTransfer intentionally exports DB data, not this timing file.
        if guestTiming && transfer != "" {
            f, readErr := fs.OpenFile("snapshot-out/startup-timing.json", os.O_RDONLY, 0)
            if readErr != nil { err = readErr; return }
            data, readErr := io.ReadAll(io.LimitReader(f, 128*1024+1))
            err = errors.Join(readErr, f.Close())
            if err != nil { return }
            if len(data) > 128*1024 { err = fmt.Errorf("oversized diagnostic timing"); return }
            if err = os.WriteFile(filepath.Join(transfer, "startup-timing.json"), data, 0600); err != nil { return }
        }
'''
    text = text.replace('\t"io"\n', '\t"io"\n\t"os"\n\t"path/filepath"\n', 1)
    text = text.replace(anchor, observe+anchor, 1)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    replacement = out/'runtime_instance.go'
    replacement.write_text(text)
    (out/'overlay.json').write_text(json.dumps({'Replace': {str(target): str(replacement)}}, indent=2)+'\n')
    (out/'identity.json').write_text(json.dumps(dict(classification='diagnostic-only post-execution copy; no adoption or Qualification claim',
        owner=OWNER, owner_sha256=EXPECTED, overlay_sha256=hashlib.sha256(replacement.read_bytes()).hexdigest(),
        product=str(args.product.resolve()), generated_files_edited=False), indent=2)+'\n')
    print(out/'overlay.json')


if __name__ == '__main__':
    main()
