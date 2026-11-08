#!/usr/bin/env python3
"""Install additive Issue130 fixtures into a separate inventoried C2 product.

No translation/build/run. Refuse changed host inputs and in-place repo edits.
The emitted receipt inventories every source before and after the overlay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Issue130 overlay anchor missing or duplicated: ' + old[:80])
    return text.replace(old, new)


def overlay(files):
    """Pure byte transform; caller checks the source receipt and writes once."""
    out = dict(files)
    for name in ('internal/nativewire/issue130_hooks.go', 'internal/nativewire/issue130_hook_test.go',
                 'issue130_native_test.go', 'internal/control/issue130_native_test.go'):
        if name in files:
            raise ValueError('refusing to overwrite existing fixture: ' + name)
    p = 'internal/nativewire/backend.go'
    s = out[p].decode()
    s = replace_once(s, 'Failure  func(error)', 'Failure  func(error)\n ConfigureIssue130 func(*Issue130Hooks)')
    s = replace_once(s, 'captureDebt                  error', 'captureDebt                  error\n issue130 *Issue130Hooks')
    s = replace_once(s, '\n\t}})', '\n\t}, func(h *Issue130Hooks) { r.issue130 = h }})')
    s = replace_once(s, 's.phase = string(f.body)', 's.phase = string(f.body)\n if r.issue130 != nil && r.issue130.ForceIdleState { s.phase = \"idle\" }')
    out[p] = s.encode()
    p = 'internal/nativewire/relay.go'
    out[p] = replace_once(out[p].decode(), 'func (s *session) relayDone(part uint8) {',
        'func (s *session) relayDone(part uint8) {\n if h := s.root.issue130; h != nil && h.RelayDone != nil { h.RelayDone(s.lease.Token(), part) }').encode()
    p = 'internal/nativewire/capture.go'
    out[p] = replace_once(out[p].decode(), 'stored.OwnRoot(image, r.build)',
                          'stored.OwnRoot(image, r.issue130Build(r.build))').encode()
    out['internal/nativewire/issue130_hooks.go'] = (HERE / 'hooks.go.txt').read_bytes()
    out['internal/nativewire/issue130_hook_test.go'] = (HERE / 'hook_unit_test.go.txt').read_bytes()
    out['internal/host/factory.go'] = (HERE / 'factory.go.txt').read_bytes()
    out['issue130_native_test.go'] = (HERE / 'public_test.go.txt').read_bytes()
    out['internal/control/issue130_native_test.go'] = (HERE / 'control_test.go.txt').read_bytes()
    return out


def inventory(product):
    files = sorted(product.rglob('*'))
    if any(p.is_symlink() for p in files):
        raise ValueError('symlink in Issue130 product')
    return {p.relative_to(product).as_posix(): sha(p.read_bytes())
            for p in files if p.is_file()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--product', type=Path, required=True)
    p.add_argument('--source-receipt', type=Path, required=True)
    p.add_argument('--output-receipt', type=Path, required=True)
    args = p.parse_args()
    product = args.product.resolve()
    if product == ROOT or ROOT.is_relative_to(product) or (product / '.git').exists():
        p.error('use a separate disposable C2 product copy')
    source = json.loads(args.source_receipt.read_text())
    if source.get('contract') != 'issue65-public-unqualified' or source.get('guest_sha256') != 'd4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481':
        p.error('expected fixed C2 UNQUALIFIED public-source receipt')
    if args.output_receipt.exists():
        p.error('use a new receipt path; preserve the original evidence')
    if args.output_receipt.resolve().is_relative_to(product):
        p.error('keep the output receipt outside the inventoried product')
    require_commit(ROOT, source['host_source_commit'])
    before = inventory(product)
    if before != source['source_inventory']:
        p.error('C2 source inventory differs')
    files = {name: (product / name).read_bytes() for name in before}
    if files.get('internal/host/factory.go') != (ROOT / 'benchmarks/spikes/issue65-p1-public/factory.go.txt').read_bytes():
        p.error('expected exact C2 native public factory preimage')
    # All three host sources must still match the bounded reviewed base.
    import subprocess
    for name in ('internal/nativewire/backend.go', 'internal/nativewire/relay.go', 'internal/nativewire/capture.go'):
        expected = subprocess.check_output(['git', 'show', 'a5ee1ed9cc2c6932d317fba77c339b364acd48df:' + name], cwd=ROOT)
        if files[name] != expected:
            p.error('host preimage changed; re-review overlay: ' + name)
    observer_commit = require_commit(ROOT, subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()).source_commit
    observer_files = [Path(__file__).resolve(), *sorted(HERE.glob('*.txt'))]
    for observer in observer_files:
        committed = subprocess.check_output(['git', 'show', observer_commit + ':' + observer.relative_to(ROOT).as_posix()], cwd=ROOT)
        if committed != observer.read_bytes():
            p.error('commit the observer inputs before staging: ' + observer.name)
    after = overlay(files)
    for name, data in after.items():
        if files.get(name) != data:
            (product / name).write_bytes(data)
    args.output_receipt.write_text(json.dumps(dict(
        contract='issue130-public-lifetime-UNEXECUTED',
        observer_source_commit=observer_commit,
        observer_files_sha256={p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in observer_files},
        input_receipt_sha256=sha(args.source_receipt.read_bytes()),
        host_source_commit=source['host_source_commit'], guest_sha256=source['guest_sha256'],
        guest_origin_source_commit=source.get('guest_origin_source_commit'),
        runtime_installer_source_commit=source.get('runtime_installer_source_commit'),
        input_source_inventory=before, source_inventory=inventory(product),
        changed_files=[n for n in after if files.get(n) != after[n]],
        fixture_sha256={p.name: sha(p.read_bytes()) for p in HERE.glob('*.txt')},
        runtime_executed=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
