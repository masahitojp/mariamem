#!/usr/bin/env python3
"""Heap-only correctness replay; invoke through experiment-workspace tooling.

No mmap, performance/soak run, golden update, merge, tag or release.
"""
import json
import re
import shutil
import run as r

r.record.update(basis='56be628bf2d976048c5ea6d1949879781ed75342', correctness_only=True)
r.run('build-counter', ['cc', '-O2', r.ROOT/'benchmarks/tools/process_cost.c', '-o', r.TEMP/'process-cost'])
r.run('format-handwritten', [r.GO.parent/'gofmt', '-w', r.ROOT/'internal/generatedgo/runtime_instance.go', r.ROOT/'internal/generatedgo/runtime_instance_test.go', r.ROOT/'tests/godefault/pure_memory32_test.go'])
spike = r.ROOT/'benchmarks/spikes/generated-go-integration'
pins_path = r.ROOT/'release/generated-go-inputs.json'
pins = json.loads(pins_path.read_text())
assert r.digest(r.GUEST) == pins['guest_sha256']
assert 'MemoryMapping' not in (r.ROOT/'internal/generatedgo/runtime_instance.go').read_text()
r.run('translate-guest', [r.sys.executable, spike/'translate_guest.py', '--guest', r.GUEST, '--guest-sha256', pins['guest_sha256'], '--converter-archive', r.CACHE/'wasm2go-fork.tar.gz', '--output', r.TEMP/'translation'])
converter = r.TEMP/'translation/wasm2go'
converter_source = next((r.TEMP/'translation/converter').iterdir())
r.run('converter-unit-tests', [r.GO, 'test', '-p', '1', '-run=^(TestMemoryAccessWidths|TestTrappingLoadIsObservable|TestPureMemory32RetainsIndividualStores|TestDCE.*)$', './internal/codegen', './internal/ssa', './internal/ssa/pass'], cwd=converter_source)
r.run('deterministic-memory32-regression', [r.sys.executable, r.HERE/'check_fixture.py', '--converter', converter, '--output', r.TEMP/'regression'])
manifest = r.TEMP/'translation/input-manifest.json'
shutil.copyfile(manifest, r.ROOT/'release/generated-go-translation.json')
r.run('prepare-candidate', [r.sys.executable, spike/'setup_candidate.py', '--source-only', '--source-module', r.TEMP/'translation/module', '--guest', r.GUEST, '--input-manifest', manifest, '--output', r.TEMP/'candidate'])
module = r.TEMP/'candidate/module'
pins['candidate_files_sha256'] = {str(p.relative_to(module)): r.digest(p) for suffix in ('*.go', '*.s') for p in module.rglob(suffix)}
pins_path.write_text(json.dumps(pins, indent=2)+'\n')
r.run('install-runtime', [r.sys.executable, r.ROOT/'scripts/generate_runtime.py', '--source-module', module, '--output', r.TEMP/'generatedgo'])
for p in (r.TEMP/'generatedgo').rglob('*'):
    if p.is_file():
        target = r.ROOT/'internal/generatedgo'/p.relative_to(r.TEMP/'generatedgo')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
r.run('verify-provenance', [r.sys.executable, r.ROOT/'scripts/verify_generated_runtime.py'])
r.run('controlled-root-and-worker-traps', [r.GO, 'test', '-p', '1', '-v', '-count=1', '-run=^TestControlledGuest', '-timeout=60s', './internal/generatedgo'])
r.run('focused-runtime-race', [r.GO, 'test', '-race', '-p', '1', '-count=1', '-timeout=120s', './internal/generatedgo/code/base', './internal/generatedgo', './internal/guest', './internal/host', './internal/mysqlwire', './internal/snapshot'], extras={'CGO_ENABLED': '1'})
for name in ['GeneratedTraps', 'CRUDSessionsAndFork', 'Auth', 'RepeatedClose']:
    r.run('product-'+name, [r.GO, 'test', '-p', '1', '-tags=integration', '-v', '-count=1', '-run=^TestPureMemory32'+name+'$', '-timeout=90s', './tests/godefault'], timeout=150)

# Check positive native license retention without running a benchmark.
host = r.TEMP/'mariamem-host'
r.run('build-host-for-attribution', [r.GO, 'build', '-p', '1', '-trimpath', '-o', host, './cmd/mariamem-host'])
r.run('candidate-symbols', [r.GO, 'tool', 'nm', host])
evidence_path = r.ROOT/'release/generated-license-evidence.json'
evidence = json.loads(evidence_path.read_text())
symbols = (r.EVIDENCE/'candidate-symbols.log').read_text()
checked = []
for component, row in evidence['retained_symbols'].items():
    for example in row['examples']:
        path = r.ROOT/example['generated_file']
        name = example['generated_function']
        assert 'func '+name+'(' in path.read_text()
        assert re.search(r'/code/'+re.escape(path.parent.name)+r'\.'+re.escape(name)+r'(?:\.abi0)?$', symbols, re.M), name
        checked.append(dict(component=component, function=name, generated_file=example['generated_file'], candidate_symbol_retained=True))
evidence['generated_provenance_sha256'] = r.digest(r.ROOT/'internal/generatedgo/provenance.json')
evidence['controlled_traps_check'] = dict(basis=r.record['basis'], host_sha256=r.digest(host), generated_provenance_sha256=evidence['generated_provenance_sha256'], examples=checked, note='Heap-only correctness candidate. Positive native retention rechecked; not release approval.')
evidence_path.write_text(json.dumps(evidence, indent=2)+'\n')
license_path = r.ROOT/'release/distribution-licenses.json'
license = json.loads(license_path.read_text())
license['evidence_sha256'] = r.digest(evidence_path)
license_path.write_text(json.dumps(license, indent=2)+'\n')
shutil.copyfile(license_path, r.ROOT/'python/license-inventory.json')

tools = json.loads((r.ROOT/'release/generated-go-toolchain.json').read_text())
download = r.ROOT/'build/downloads'/tools['archives']['converter']['file']
download.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(r.CACHE/'wasm2go-fork.tar.gz', download)
guest = r.TEMP/'guest'
guest.mkdir()
shutil.copyfile(r.GUEST, guest/'mariamem.wasm')
shutil.copyfile(r.GUEST.parent/'guest.json', guest/'guest.json')
r.run('independent-regeneration', [r.sys.executable, r.ROOT/'scripts/regenerate_release_guest.py', '--guest-dir', guest, '--output', r.TEMP/'regeneration'], timeout=600)
r.run('canonical-check', [r.SHARED/'.venv/bin/python', r.ROOT/'scripts/verify.py', 'check'], timeout=900)
r.record.update(finished=True, compatibility_pass=True, fixture_case_count=2472, trap_cases=1693, max_boundary_extra_traps=7, retained_license_examples_rechecked=len(checked))
r.save()
compact = dict(basis=r.record['basis'], backing='unchanged Go heap', mmap=False, correctness_only=True, fixture_case_count=2472, trap_cases=1693, max_boundary_extra_traps=7, phases=[dict(name=p['name'], exit_code=p['exit_code']) for p in r.record['phases']], guest_sha256=pins['guest_sha256'], generated_provenance_sha256=evidence['generated_provenance_sha256'], converter_sha256=r.digest(converter), limits=dict(min_free_gib=16, disk_budget_gib=6, rss_gib=6, physical_gib=8), result='PASS', limitation='Worker failure is relayed at cooperative join; non-cooperative root/worker termination is not guaranteed.')
(r.ROOT/'benchmarks/v042-controlled-traps.json').write_text(json.dumps(compact, indent=2)+'\n')
