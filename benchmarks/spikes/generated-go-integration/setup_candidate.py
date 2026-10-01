#!/usr/bin/env python3
"""Build a selected, checksum-bound local candidate after the FD gate passes.

Uses the accepted pinned generated module; NOT the full release source pipeline.
No runtime is enabled in the normal package or published by this command.
"""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-module', type=Path, required=True)
    p.add_argument('--guest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument("--input-manifest", type=Path, default=HERE/"accepted-generated-source.json", help="explicit guest and generated-source identity; never inferred from the candidate")
    a = p.parse_args()
    input_manifest = a.input_manifest.resolve()
    pins = json.loads(input_manifest.read_text())
    guest_sha = pins["guest_sha256"]
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        p.error('this local candidate recipe is macOS arm64 only; Ubuntu acceptance is pending')
    if digest(a.guest) != guest_sha:
        p.error('guest differs from the accepted converter input')
    out = a.output.resolve()
    if out.exists():
        p.error('output must be fresh')
    module = out/'module'
    subprocess.run([sys.executable, str(HERE/'setup_audit.py'), '--source-module', str(a.source_module), '--output', str(module), '--input-manifest', str(input_manifest)], check=True)
    driver = (module/'main.go').read_text()
    def change(old, new):
        if driver.count(old) != 1:
            raise ValueError('candidate driver fragment changed: '+repr(old[:80]))
        return driver.replace(old, new, 1)

    # Drop diagnostic I/O overrides entirely: no formatting or metadata lookup
    # is charged to ordinary guest execution. Retain diagnostic driver separately.
    begin = driver.index('func (h *host) Fd_pread(')
    end = driver.index('func (f entropyFS) Readlink(', begin)
    driver = driver[:begin]+driver[end:]
    driver = change('"encoding/binary"', '"encoding/binary"\n"crypto/sha256"\n"io"')
    driver = change('// Compatibility preflight only: recognize the unchanged host\'s transfer paths.', '// Selected candidate: bind compiled code to the host-verified module.')
    driver = change('if len(os.Args) > 2 && os.Args[1] == "run" {', 'if len(os.Args) > 2 && os.Args[1] == "run" {\n verifyCompiledGuest(os.Args[2])')
    driver = change('if restore != "" {', 'var maps *base.PreparedFiles\n if restore != "" {')
    driver = change('if err := loadTransfer(fs, filepath.Join(restore, "data"), "mariadb"); err != nil {\n\t\t\tpanic(err)\n\t\t}', 'var err error\n maps, err = base.MapPreparedFiles(fs, filepath.Join(restore, "data"), "mariadb")\n if err != nil { panic(err) }')
    driver = change('\n}\n\nfunc (h *host) Fd_dup(', '\n if err := maps.Close(); err != nil { panic(err) }\n}\n\nfunc (h *host) Fd_dup(')
    driver += '''
// The host still validates manifest/module/snapshot trust. This additional
// check prevents presenting a different validated WASM to this compiled guest.
func verifyCompiledGuest(name string) {
 f, err := os.Open(name); if err != nil { panic(err) }; defer f.Close()
 h := sha256.New(); if _,err = io.Copy(h,f); err != nil { panic(err) }
 if fmt.Sprintf("%x",h.Sum(nil)) != compiledGuestSHA256 { panic("compiled guest/module identity mismatch") }
}
'''
    (module/'main.go').write_text(driver)
    (module/'guest_identity.go').write_text('package main\nconst compiledGuestSHA256 = '+json.dumps(guest_sha)+'\n')
    shutil.copyfile(HERE/'prepared-files.go.txt', module/'generated/base/prepared_files.go')
    shutil.copyfile(HERE/'prepared-files-test.go.txt', module/'generated/base/prepared_files_test.go')
    shutil.copyfile(HERE/'prepared-growth-test.go.txt', module/'generated/base/prepared_growth_test.go')
    env = dict(os.environ, GOTOOLCHAIN='go1.26.8')
    sources = sorted(module.rglob('*.go'))
    subprocess.run(['gofmt','-w', *map(str,sources)], check=True)
    subprocess.run(['go','test','-race','./generated/base'], cwd=module, env=env, check=True)
    native = out/'native'; native.mkdir()
    subprocess.run(['go','build','-p','1','-trimpath','-o',str(native/'wasmer-headless'),'.'], cwd=module,env=env,check=True)
    subprocess.run(['go','build','-trimpath','-o',str(native/'mariamem-host'),'./cmd/mariamem-host'], cwd=ROOT,env=env,check=True)
    shutil.copyfile(a.guest,native/'mariamem.wasmu')
    shutil.copyfile(Path(str(a.guest)+'.json'),native/'mariamem.wasmu.json')
    manifest = dict(version=1,platform='darwin-arm64',minimum_macos=15,public_release_ready=False,runtime_kind='generated-go',sha256={n:digest(native/n) for n in ['wasmer-headless','mariamem-host','mariamem.wasmu','mariamem.wasmu.json']})
    (native/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    provenance = dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),guest_sha256=guest_sha,input_manifest_sha256=digest(input_manifest),go_toolchain='go1.26.8',converter_commit='ac98bcf00c17d8531f0c071a9836d0b50975e7ff',templates_sha256={str(f.relative_to(HERE)):digest(f) for f in sorted(HERE.iterdir()) if f.is_file()},generated_go_sha256={str(f.relative_to(module)):digest(f) for f in sources},generated_asm_sha256={str(f.relative_to(module)):digest(f) for f in sorted(module.rglob('*.s'))},native_manifest=manifest,scope='selected local candidate; full source regeneration and Ubuntu acceptance pending')
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(native)

if __name__ == '__main__':
    main()
