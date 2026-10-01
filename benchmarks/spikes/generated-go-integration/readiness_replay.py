#!/usr/bin/env python3
"""Fail-closed clean-source replay; local verification, never release publication.

Requires explicitly supplied pinned cache inputs. No pre-generated Go or old
object files are copied. The Linux-arm64 SDK image is a recorded local bridge,
not the missing canonical Linux-x86_64 production toolchain handoff.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[3]
IMAGE = 'sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f'
CONVERTER_ARCHIVE = '1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f'
GUEST = '6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3'

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--downloads', type=Path, required=True)
    p.add_argument('--converter-archive', type=Path, required=True)
    p.add_argument('--translation-only-guest', type=Path, help='explicit partial replay; does NOT count as guest regeneration')
    p.add_argument('--guest-build-only', action='store_true', help='source-to-legacy-EH build only; compare independent recipe outputs, not historical artifact identity')
    p.add_argument('--llvm-dir', type=Path, help='explicit isolated compiler override; requires guest-build-only, never automatically changes accepted identity')
    a = p.parse_args(); out = a.output.resolve()
    if a.llvm_dir and not a.guest_build_only: p.error('llvm override requires guest-build-only')
    if a.guest_build_only and a.translation_only_guest: p.error('guest-build-only requires a full source build')
    if out.exists(): p.error('output must be fresh')
    if sha(a.converter_archive) != CONVERTER_ARCHIVE: p.error('converter archive mismatch')
    out.mkdir(parents=True); (out/'go.mod').write_text('module example.com/readiness-replay\n\ngo 1.26.0\n')
    report = {'source_sha': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(), 'completed': False, 'stages': [], 'full_guest_regeneration': not bool(a.translation_only_guest)}
    env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOWORK='off')
    def save(): (out/'replay.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(name, cmd, cwd=out, timeout=3600):
        start = time.monotonic()
        with (out/(name+'.log')).open('w') as f:
            r = subprocess.run(list(map(str, cmd)), cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, timeout=timeout)
        report['stages'].append({'name':name,'seconds':time.monotonic()-start,'exit_code':r.returncode,'log_sha256':sha(out/(name+'.log'))}); save()
        if r.returncode: raise RuntimeError(name+' failed; see log')
    try:
        product = out/'product'; product.mkdir()
        archive = subprocess.check_output(['git','archive',report['source_sha']], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as t: t.extractall(product, filter='data')
        if a.translation_only_guest:
            guest = a.translation_only_guest.resolve()
        else:
            lock = json.loads((product/'release/inputs.lock.json').read_text())
            cache = product/'build/downloads'; cache.mkdir(parents=True)
            for item in lock['inputs']:
                if item['name'] in ['lite4mariadb','libmariadb','wolfssl','pcre2','libfmt']:
                    src=a.downloads/item['file']
                    if sha(src)!=item['sha256']: raise ValueError('source archive mismatch: '+item['name'])
                    shutil.copyfile(src,cache/item['file'])
            run('prepare', ['python3', product/'scripts/prepare_guest.py'])
            report['prepared_source'] = json.loads((product/'build/prepared-source.json').read_text()); save()
            work = out/'work'; work.mkdir(); shutil.move(product/'build/source',work/'source')
            for name in ['legacy_eh_toolchain.sh','eh_probe.cpp']: shutil.copyfile(product/'benchmarks/spikes/wasm2go'/name,work/name)
            actual = subprocess.check_output(['docker','image','inspect',IMAGE,'--format','{{.Id}}'], text=True).strip()
            if actual != IMAGE: raise ValueError('Docker image identity mismatch')
            report['toolchain_image_id']=actual; save()
            cmd=['docker','run','--rm','--network','none','--platform','linux/arm64','--mount',f'type=bind,src={work},dst=/work',IMAGE,'bash','/work/legacy_eh_toolchain.sh']
            if a.llvm_dir:
                llvm=a.llvm_dir.resolve()
                for name in ['clang','wasm-ld','llvm-ar','llvm-ranlib']:
                    if not (llvm/'bin'/name).is_file(): raise ValueError('missing LLVM override tool: '+name)
                report['llvm_override']={'host_path':str(llvm),'tools_sha256':{name:sha(llvm/'bin'/name) for name in ['clang','wasm-ld','llvm-ar','llvm-ranlib']}}
                cmd[cmd.index(IMAGE):cmd.index(IMAGE)]=['--mount',f'type=bind,src={llvm},dst=/root/.wasixcc/llvm,readonly','--env','LD_LIBRARY_PATH=/root/.wasixcc/llvm/lib']
                save()
            run('toolchain-probe',cmd+['probe'])
            run('guest-build',cmd+['build-no-postopt'])
            run('guest-postopt',cmd+['postopt'])
            guest=work/'artifact/mariamem-legacy-eh-O2-compatible.wasm'
        report['guest_sha256']=sha(guest); report['guest_size']=guest.stat().st_size
        report['accepted_guest_identity_match']=sha(guest)==GUEST
        if not a.translation_only_guest:
            raw=work/'artifact/mariamem-legacy-eh.wasm'
            report['linked_guest_sha256']=sha(raw); report['linked_guest_size']=raw.stat().st_size
            report['build_paths']={'container_source':'/work/source', 'container_build':'/work/source/build-legacy-no-postopt', 'host_work':str(work)}
        save()
        if a.guest_build_only:
            report['completed']=True; report['comparison_scope']='same v0.4 legacy-EH recipe, not historical/new-EH identity'; return
        if sha(guest)!=GUEST: raise ValueError('rebuilt guest differs from accepted identity; no silent pin update')
        croot=out/'converter'; croot.mkdir()
        with tarfile.open(a.converter_archive) as t: t.extractall(croot,filter='data')
        converter=next(croot.iterdir())
        for name in ['imported-memory.patch','import-function-index.patch']:
            run('patch-'+name,['git','apply','--unidiff-zero',product/'benchmarks/spikes/wasm2go'/name],converter)
        run('converter-build',['go','build','-mod=readonly','-trimpath','-o',out/'wasm2go','./cmd/wasm2go'],converter)
        translated=out/'translated'; translated.mkdir(); (translated/'go.mod').write_text('module example.com/mariamem-spike\n\ngo 1.26.0\n')
        run('translate',[out/'wasm2go','-pure','-i',guest,'-out-dir',translated/'generated','-pkg','generated','-import','example.com/mariamem-spike/generated'])
        (translated/'generated/base/spike_wait.go').write_text('package base\nfunc SpikeWait(m *Module) { m.Threads.wg.Wait() }\n')
        shutil.copyfile(product/'benchmarks/spikes/wasm2go/wait-contract-test.go.txt',translated/'generated/base/spike_contract_test.go')
        pins=json.loads((product/'benchmarks/spikes/generated-go-integration/accepted-generated-source.json').read_text())
        actual={str(f.relative_to(translated/'generated')):sha(f) for f in (translated/'generated').rglob('*') if f.is_file()}
        if actual!=pins['files_sha256']: raise ValueError('fresh generator output inventory mismatch')
        report['generated_inventory_match']=True; report['generated_bytes']=sum(f.stat().st_size for f in (translated/'generated').rglob('*') if f.is_file()); report['converter_sha256']=sha(out/'wasm2go');save()
        metadata=Path(str(guest)+'.json')
        if not metadata.exists(): metadata.write_text(json.dumps({'wasm_sha256':GUEST,'module_sha256':GUEST,'snapshot_version':1})+'\n')
        run('candidate-build',['python3',product/'benchmarks/spikes/generated-go-integration/setup_candidate.py','--source-module',translated,'--guest',guest,'--output',out/'candidate'])
        report['native_manifest']=json.loads((out/'candidate/native/manifest.json').read_text()); report['completed']=True
    except Exception as e:
        report['failure']=str(e); raise
    finally: save()

if __name__=='__main__': main()
