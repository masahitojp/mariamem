"""Selected development producer receipts; never release or binding approval.

The registered inputs are the trust root. Receipts bind those inputs to a clean
producer and independent source builds, rather than falling back to root inputs.
"""
import hashlib
import json
from pathlib import Path
import stat

from common import digest
from guest_preparation_context import resolve

CONTRACT = 'selected-development-guest-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    # Same on-disk serialization as prepare_selected's private input view.
    return (json.dumps(value, indent=2) + '\n').encode()


def tree_identity(source):
    """Hash full prepared contents, modes and link targets before compilation."""
    entries = []
    for p in sorted(source.rglob('*')):
        mode = p.lstat().st_mode
        if stat.S_ISLNK(mode):
            value = ['link', p.readlink().as_posix()]
        elif stat.S_ISDIR(mode):
            value = ['directory']
        elif stat.S_ISREG(mode):
            value = ['file', digest(p)]
        else:
            raise ValueError('unsupported prepared source member: ' + str(p))
        entries.append([p.relative_to(source).as_posix(), stat.S_IMODE(mode), *value])
    return {'members': len(entries), 'sha256': hashlib.sha256(encoded(entries)).hexdigest()}


def verify_preparation(resolved, prepared):
    guest = resolved['guest_input']
    overlays = {Path(name).name: ref['sha256'] for name, ref in resolved['files'].items()
                if Path(name).parent == Path('guest')}
    overlays['input.json'] = hashlib.sha256(encoded(guest)).hexdigest()
    require(prepared.get('schema') == 'selected-source-preparation-v1' and
            prepared.get('release_eligible') is False, 'unknown selected preparation contract')
    require(prepared.get('selection') == resolved['selection'] and
            prepared.get('guest_input') == guest and
            prepared.get('resolved_input_sha256') == hashlib.sha256(encoded(resolved)).hexdigest() and
            prepared.get('inputs_lock_sha256') == hashlib.sha256(encoded(resolved['effective_lock'])).hexdigest() and
            prepared.get('overlays') == overlays, 'selected preparation input identity mismatch')
    require(prepared.get('portability_series') == guest['patches'], 'selected patch order mismatch')
    for field in ('source_overlay', 'observation_overlay'):
        if field in guest:
            require(prepared.get(field) == [guest[field]], 'selected overlay mismatch: ' + field)
    require(prepared.get('experimental') == ('native_overlay' in guest), 'selected profile mismatch')
    if 'native_overlay' in guest:
        require(prepared.get('experimental_patch') == {
            'file': guest['native_overlay']['file'], 'sha256': guest['native_overlay']['sha256']},
            'selected native overlay mismatch')


def verify_record(root, directory, record, *, engine, profile):
    """Called after the ordinary clean-source/toolchain checks by dev_guest."""
    from dev_guest import inventory
    require(engine is not None and profile is not None,
            'selected guest requires explicit expected --engine and --profile')
    expected = resolve(root, engine, profile)
    require(record.get('selected_inputs') == expected, 'selected guest version/profile/input mismatch')
    require(record.get('source_commit') == record['source_identity']['commit'], 'selected producer mismatch')
    verify_preparation(expected, record['prepared_source'])
    builds = record.get('source_builds', [])
    require(len(builds) >= 2 and len(builds) == len(record['repetitions']),
            'selected guest requires independent source builds')
    for index, build in enumerate(builds):
        require(build.get('trial') == index and build.get('allocator_contract') == 'PASS',
                'selected source build/allocator receipt mismatch')
        require(build.get('prepared_source') == record['prepared_source'], 'mixed source preparations')
        tree = build.get('prepared_tree', {})
        require(isinstance(tree.get('members'), int) and tree['members'] > 0 and
                isinstance(tree.get('sha256'), str) and len(tree['sha256']) == 64,
                'missing prepared source inventory')
        require(tree == builds[0]['prepared_tree'], 'independent prepared sources differ')
    actual = inventory(directory)
    actual.pop('guest.json', None)
    require(record.get('artifacts_sha256') == actual, 'selected producer artifact inventory mismatch')


def translate_for_binding(root, guest, output, *, engine, profile):
    """Obtain actual new function bodies for review without accepting a binding."""
    import os
    import sys
    from build_generated_guest import download
    from build_feedback import go_environment, run
    from dev_guest import external_output, source_identity, verify_guest, verify_translation, write
    record = verify_guest(root, guest, engine=engine, profile=profile)
    identity = source_identity(root)
    out = external_output(root, output)
    out.mkdir(parents=True)
    try:
        tools = json.loads((root/'release/generated-go-toolchain.json').read_text())
        converter = download(tools['archives']['converter'], out/'downloads')
        translation = out/'translation'
        env = go_environment(dict(os.environ, GOTOOLCHAIN='go1.26.10', GOWORK='off',
                                  GOENV='off', GOFLAGS='', GOEXPERIMENT=''))
        run([sys.executable, root/'benchmarks/spikes/generated-go-integration/translate_guest.py',
             '--guest', guest/'mariamem.wasm', '--guest-sha256', record['guest_sha256'],
             '--converter-archive', converter, '--output', translation],
            env=env, check=True, phase='selected:translation',
            inputs=[guest/'guest.json', guest/'mariamem.wasm'],
            outputs=[translation/'input-manifest.json'])
        raw = verify_translation(root, translation, record['guest_sha256'])
        require(verify_guest(root, guest, engine=engine, profile=profile) == record and
                source_identity(root) == identity, 'selected translation inputs changed')
        write(out/'binding-inputs.json', {
            'contract': CONTRACT, 'result': 'BINDING_REVIEW_REQUIRED',
            'selection': record['selected_inputs']['selection'],
            'resolved_sha256': record['selected_inputs']['resolved_sha256'],
            'producer_source_commit': record['source_commit'],
            'translation_source_commit': identity['commit'],
            'guest_sha256': record['guest_sha256'], 'guest_record_sha256': digest(guest/'guest.json'),
            'translation_record_sha256': digest(translation/'input-manifest.json'),
            'raw_translation': raw,
            'binding': 'NOT_REVIEWED', 'public_acceptance': 'NOT_RUN'})
    except BaseException as exc:
        write(out/'failure.json', {'contract': CONTRACT, 'result': 'FAILED',
                                  'exception': type(exc).__name__, 'message': str(exc)})
        raise
    print('New selected translation saved; binding review and public acceptance remain required')

