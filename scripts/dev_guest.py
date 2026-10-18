"""Bindings for the explicit UNQUALIFIED guest route; not release evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
from common import digest

CONTRACT = 'development-unqualified-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write(path, record):
    Path(path).write_text(json.dumps(record, indent=2, sort_keys=True)+'\n')


def external_output(root, output):
    output = Path(output)
    require(output.is_absolute() and output.resolve() == output,
            'dev output must be an absolute non-symlink path')
    require(not output.is_relative_to(root.resolve()) and not root.resolve().is_relative_to(output),
            'dev output must be outside the source checkout, never a Release/canonical directory')
    require(not set(output.parts) & {'generated-release','release-regeneration','_native','release','internal'},
            'dev output must not use a Release/canonical namespace')
    require(not output.exists(), 'dev output must be fresh')
    return output


def inventory(root):
    root = Path(root)
    result = {}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(), 'symlink in dev artifact: '+str(p))
        if p.is_file():
            result[p.relative_to(root).as_posix()] = digest(p)
    return result


def source_identity(root):
    def git(*args):
        return subprocess.check_output(['git', '-c', 'safe.directory='+str(root), *args], cwd=root)
    require(not git('status', '--porcelain').strip(), 'dev build requires committed clean source')
    names = git('ls-files', '-z').decode().split('\0')
    files = {}
    for name in names:
        if name:
            p = root/name
            require(p.is_file() and not p.is_symlink(), 'invalid source file: '+name)
            files[name] = digest(p)
    return {'commit': git('rev-parse', 'HEAD').decode().strip(), 'files_sha256': files}


def verify_source_origin(root, origin):
    """Keep the guest's immutable origin; bind host-only fixes separately.

    Unchanged source is checked against the live clean tree. For changed host
    stage/docs/tests files, validate the old bytes against the actual Git commit.
    Guest preparation/build/tool scripts and all other inputs still fail closed.
    This is a narrow stage boundary, not arbitrary cross-commit receipt adoption.
    """
    current = source_identity(root)
    if origin == current:
        return
    from git_identity import require_commit
    try:
        require_commit(root, origin['commit'])
        def git(*args):
            return subprocess.check_output(['git','-c','safe.directory='+str(root),*args],cwd=root)
        old_names = set(git('ls-tree','-r','--name-only',origin['commit']).decode().splitlines())
        require(set(origin['files_sha256']) == old_names, 'guest origin source inventory missing/mismatched')
        changed = set(git('diff','--name-only',origin['commit'],current['commit']).decode().splitlines())
        host_stages = {'scripts/dev_guest.py','scripts/generate_runtime.py','scripts/regenerate_release_guest.py',
                       'scripts/runtime_thread_lifetime.py',
                       'internal/mysqlwire/wire.go','internal/mysqlwire/multi_spike_test.go'}
        require(all(n in host_stages or n.startswith(('docs/','tests/')) for n in changed),
                'guest source/build inputs changed; fresh guest build required')
        for name, sha in origin['files_sha256'].items():
            actual = (hashlib.sha256(git('show',origin['commit']+':'+name)).hexdigest()
                      if name in changed else current['files_sha256'].get(name))
            require(actual == sha, 'guest historical source hash mismatch: '+name)
    except subprocess.CalledProcessError as exc:
        raise ValueError('guest source origin is not available/verifiable') from exc


def verify_guest(root, directory):
    directory = Path(directory)
    record = json.loads((directory/'guest.json').read_text())
    require(record['contract'] == CONTRACT and record['result'] == 'UNQUALIFIED', 'not a dev guest contract')
    verify_source_origin(root, record['source_identity'])
    pins = json.loads((root/'release/generated-go-toolchain.json').read_text())
    tools = record['toolchain']
    require(tools['pins_sha256'] == digest(root/'release/generated-go-toolchain.json') and
            tools['archives_sha256'] == {k:v['sha256'] for k,v in pins['archives'].items()},
            'dev toolchain identity mismatch')
    require(record['prepared_source']['inputs_lock_sha256'] == digest(root/'release/inputs.lock.json') and
            record['prepared_source']['overlays'] == {p.name:digest(p) for p in (root/'guest').iterdir() if p.is_file()},
            'dev source/patch identity mismatch')
    require(record['guest_sha256'] == digest(directory/'mariamem.wasm') and
            record['guest_bytes'] == (directory/'mariamem.wasm').stat().st_size,
            'dev Wasm identity mismatch')
    require(len(record['repetitions']) == 1 and record['repetitions'][0] == {
        'guest_sha256': record['guest_sha256'], 'linked_sha256': digest(directory/'linked.wasm')},
        'dev linked/build identity mismatch')
    return record


def verify_translation(root, out, guest_sha):
    raw = json.loads((out/'input-manifest.json').read_text())
    tools = json.loads((root/'release/generated-go-toolchain.json').read_text())
    patches = root/'benchmarks/spikes/wasm2go'
    require(raw['guest_sha256'] == guest_sha and digest(out/'guest.wasm') == guest_sha,
            'translation guest identity mismatch')
    require(raw['converter_commit'] == json.loads((root/'release/generated-go-translation.json').read_text())['converter_commit'] and
            raw['converter_archive_sha256'] == tools['archives']['converter']['sha256'] and
            raw['patched_converter_sha256'] == digest(out/'wasm2go') and
            raw['patches_sha256'] == {name:digest(patches/name) for name in raw['patches_sha256']} and
            set(raw['patches_sha256']) == set(json.loads((root/'release/generated-go-translation.json').read_text())['patches_sha256']),
            'translation tool/patch identity mismatch')
    require(raw['files_sha256'] == inventory(out/'module/generated'), 'stale/mixed generated translation')
    return raw


def install_inputs(record, module, root=None):
    require(record['contract'] == CONTRACT and record['result'] == 'UNQUALIFIED', 'not dev installation inputs')
    for key in ('guest_record_sha256', 'translation_record_sha256', 'guest_sha256'):
        require(len(record[key]) == 64 and all(c in '0123456789abcdef' for c in record[key]), 'invalid dev provenance: '+key)
    if root is not None:
        guest = Path(record['guest_directory'])
        translation = Path(record['translation_directory'])
        actual = verify_guest(root, guest)
        require(digest(guest/'guest.json') == record['guest_record_sha256'] and
                actual['guest_sha256'] == record['guest_sha256'], 'dev acquisition provenance mismatch')
        verify_translation(root, translation, record['guest_sha256'])
        require(digest(translation/'input-manifest.json') == record['translation_record_sha256'],
                'dev translation provenance mismatch')
    require(record['source_inventory'] == inventory(module), 'dev candidate source identity mismatch')
    require(record['data_sha256'] == digest(module/'generated/data.bin'), 'dev data identity mismatch')
    return record


def regenerate_development(root, guest, output):
    """Existing regeneration stages, with bound dev inputs and an isolated host copy."""
    import os
    import shutil
    import sys
    from build_generated_guest import download
    from build_feedback import go_environment, run
    record = verify_guest(root, guest)
    host_identity = source_identity(root)
    out = external_output(root, output)
    out.mkdir(parents=True)
    env = go_environment(dict(os.environ, GOTOOLCHAIN='go1.26.8', GOWORK='off', GOENV='off'))
    try:
        tools = json.loads((root/'release/generated-go-toolchain.json').read_text())
        converter = download(tools['archives']['converter'], out/'downloads')
        spike = root/'benchmarks/spikes/generated-go-integration'
        translation = out/'translation'
        run([sys.executable, str(spike/'translate_guest.py'), '--guest', str(guest/'mariamem.wasm'),
             '--guest-sha256', record['guest_sha256'], '--converter-archive', str(converter),
             '--output', str(translation)], env=env, check=True, phase='dev:translation',
            inputs=[guest/'guest.json', guest/'mariamem.wasm'], outputs=[translation/'input-manifest.json'])
        raw = verify_translation(root, translation, record['guest_sha256'])
        run([sys.executable, str(spike/'setup_candidate.py'), '--source-only',
             '--source-module', str(translation/'module'), '--guest', str(guest/'mariamem.wasm'),
             '--input-manifest', str(translation/'input-manifest.json'), '--output', str(out/'candidate')],
            env=env, check=True, phase='dev:source-adapter')
        module = out/'candidate/module'
        inputs = {'contract':CONTRACT, 'result':'UNQUALIFIED', 'guest_sha256':record['guest_sha256'],
                  'source_inventory':inventory(module), 'data_sha256':digest(module/'generated/data.bin'),
                  'candidate_files_sha256':{p.relative_to(module).as_posix():digest(p)
                       for suffix in ('*.go','*.s') for p in module.rglob(suffix)},
                  'guest_directory':str(guest), 'translation_directory':str(translation),
                  'guest_record_sha256':digest(guest/'guest.json'),
                  'translation_record_sha256':digest(translation/'input-manifest.json')}
        write(out/'installation-inputs.json', inputs)
        # Only committed source is copied; never old generated code/native binaries.
        product = out/'product'
        for name in host_identity['files_sha256']:
            if name.startswith('internal/generatedgo/'):
                continue
            target = product/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root/name, target)
        staged_runtime = out/'generatedgo'
        runtime = product/'internal/generatedgo'
        run([sys.executable, str(root/'scripts/generate_runtime.py'), '--source-module', str(module),
             '--development-input', str(out/'installation-inputs.json'), '--output', str(staged_runtime)],
            env=env, check=True, phase='dev:installation', outputs=[staged_runtime/'provenance.json'])
        shutil.move(str(staged_runtime), runtime)
        # The compiled host compatibility identity must refer to this guest too.
        kind = product/'internal/runtimekind/kind.go'
        old = json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256']
        text = kind.read_text()
        require(text.count('const GuestSHA256 = "'+old+'"') == 1, 'host identity anchor changed')
        kind.write_text(text.replace('const GuestSHA256 = "'+old+'"',
                                    'const GuestSHA256 = "'+record['guest_sha256']+'"'))
        generated_inventory = inventory(runtime)
        host_sources = inventory(product)
        host = out/'mariamem-dev-host'
        run(['go','build','-p','1','-trimpath','-buildvcs=false','-o',str(host),'./cmd/mariamem-host'],
            cwd=product, env=env, check=True, phase='dev:generated-go-compilation',
            inputs=[out/'installation-inputs.json', runtime/'provenance.json'], outputs=[host])
        require(inventory(runtime) == generated_inventory, 'generated source changed during compilation')
        info = run([str(host),'--snapshot-info'], env=env, check=True, capture_output=True, text=True,
                   phase='dev:binary-identity')
        require(json.loads(info.stdout)['wasm_sha256'] == record['guest_sha256'], 'wrong compiled host guest')
        # Explicit host and SDK from the isolated product copy; no installed-wheel fallback.
        smoke_env = dict(env, PYTHONPATH=str(product/'python'), MARIAMEM_TEST_HOST=str(host))
        run([sys.executable, '-m', 'pytest', str(root/'tests/test_dev_guest_smoke.py'), '-q'],
            cwd=product, env=smoke_env, check=True, phase='dev:sql-smoke', inputs=[host])
        require(verify_guest(root,guest) == record and source_identity(root) == host_identity and
                inventory(runtime) == generated_inventory and
                all(digest(product/name) == sha for name,sha in host_sources.items()),
                'source/guest/generated identity changed during smoke')
        write(out/'development.json', {'contract':CONTRACT, 'result':'UNQUALIFIED',
              'smoke':'PASS', 'source_identity':record['source_identity'],
              'host_source_identity':host_identity,
              'guest_sha256':record['guest_sha256'], 'guest_record_sha256':digest(guest/'guest.json'),
              'raw_translation':raw, 'generated_inventory':generated_inventory,
              'host_source_inventory':host_sources,
              'binary_sha256':digest(host), 'binary_bytes':host.stat().st_size,
              'go_buildinfo':subprocess.check_output(['go','version','-m',str(host)],env=env,text=True),
              'installation_inputs_sha256':digest(out/'installation-inputs.json')})
    except BaseException as exc:
        write(out/'failure.json', {'contract':CONTRACT, 'result':'FAILED',
              'guest_sha256':record['guest_sha256'], 'exception':type(exc).__name__, 'message':str(exc)})
        raise
    print('UNQUALIFIED development guest: SQL smoke PASS; no Release eligibility')
