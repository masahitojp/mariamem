"""Canonical transpilation checks remain fail-closed without obsolete images."""
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('generated_runtime_inventory', ROOT/'scripts/verify_generated_runtime.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture
def canonical(tmp_path, monkeypatch):
    source = tmp_path/'internal/generatedgo'
    source.mkdir(parents=True)
    # Minimal inert inventory still stages each independently owned primitive.
    # Use the owner directory, not the installer's list, to catch omissions.
    import shutil
    owner = tmp_path/'scripts/runtime_correctness'
    shutil.copytree(ROOT/'scripts/runtime_correctness', owner)
    for template in owner.glob('*.txt'):
        target = source/'code/base'/template.name.removesuffix('.txt')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, target)
    pins = tmp_path/'release/generated-go-inputs.json'
    pins.parent.mkdir()
    pins.write_text(json.dumps({'guest_sha256': 'a'*64}))
    generated = source/'entry.go'
    generated.write_text('package generatedgo\n')
    record = {'input_manifest_sha256': verifier.digest(pins), 'guest_sha256': 'a'*64,
              'files_sha256': {'entry.go': verifier.digest(generated)}}
    (source/'provenance.json').write_text(json.dumps(record))
    monkeypatch.setattr(verifier, 'ROOT', tmp_path)
    return tmp_path


def test_canonical_inventory_needs_no_executable_image(canonical):
    assert not (canonical/'internal/builtinruntime').exists()
    verifier.main()


@pytest.mark.parametrize('change', ['modified', 'extra', 'missing', 'pins', 'guest'])
def test_canonical_identity_changes_are_rejected(canonical, change):
    source = canonical/'internal/generatedgo'
    if change == 'modified':
        (source/'entry.go').write_text('modified')
    elif change == 'extra':
        (source/'extra.go').write_text('extra')
    elif change == 'missing':
        (source/'entry.go').unlink()
    elif change == 'pins':
        (canonical/'release/generated-go-inputs.json').write_text('{}')
    else:
        path = source/'provenance.json'
        record = json.loads(path.read_text())
        record['guest_sha256'] = 'b'*64
        path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        verifier.main()


def test_clean_installer_preserves_every_handwritten_file(tmp_path, monkeypatch):
    """Exercise the real install/copy path without translating or building Go.

    Derive expected glue from committed provenance, not the installer's own list:
    omitting new ownership files from that list must fail this test.
    """
    import hashlib
    import sys
    spec = importlib.util.spec_from_file_location('runtime_installer', ROOT/'scripts/generate_runtime.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    canonical = ROOT/'internal/generatedgo'
    record = json.loads((canonical/'provenance.json').read_text())
    handwritten = {p.relative_to(canonical).as_posix() for p in canonical.rglob('*')
                   if p.is_file() and p.name != 'provenance.json'} - set(record['files_sha256'])
    assert {'code/base/owned_prepared.go', 'code/base/owned_prepared_test.go'} <= handwritten
    project, module, output = tmp_path/'project', tmp_path/'input', tmp_path/'output'
    for name in handwritten:
        target = project/'internal/generatedgo'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((canonical/name).read_bytes())
    import shutil
    shutil.copytree(ROOT/'scripts/runtime_correctness', project/'scripts/runtime_correctness')
    (module/'generated/base').mkdir(parents=True)
    unit = module/'generated/base/unit.go'
    unit.write_text('package base\n')
    # The installer now binds a real single-guest allocation ABI. Keep this
    # inclusion test small while supplying checked raw function preimages;
    # do not mock/disable that input guard or reduce the ownership assertions.
    import re
    from runtime_atomic_loads import SUBWORD, CMP
    from runtime_thread_lifetime import FUNCTIONS, GUEST_SHA256, function
    (module/'generated/base/base.go').write_text(
        'package base\nimport (\n\t"strings"\n)\ntype Module struct {\n\tThreadStart func(*Module, int32, int32)\n}\n'
        + SUBWORD + '\n' + CMP + '\n'
        + 'func (w *WasiStubs) Sched_yield(m *Module) int32 {\n\truntime.Gosched()\n\treturn _wasiESUCCESS\n}\n'
        + 'const _wasiESUCCESS int32 = 0\n'
        + (ROOT/'tests/fixtures/pinned-worker-failure.go.txt').read_text()
        + (ROOT/'tests/fixtures/pinned-memfs.go.txt').read_text())
    for relative, (fn, _) in FUNCTIONS.items():
        body = function((canonical/relative).read_text(), fn)
        if fn == 'Fn153':
            body = re.sub(r'(func Fn153\(m \*base.Module, l0 int32\) \{\n)\s*if base.DeferThreadAllocationFree\(m, l0\) \{\s*return\s*\}\n', r'\1', body, count=1)
        target = module/'generated'/relative.removeprefix('code/')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('package generated\n'+body)
    data = b'fixture data'
    (module/'generated/data.bin').write_bytes(data)
    (project/'release').mkdir()
    (project/'release/generated-go-inputs.json').write_text(json.dumps({
        'candidate_files_sha256': {p.relative_to(module).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in module.rglob('*.go')},
        'data_sha256': hashlib.sha256(data).hexdigest(), 'guest_sha256': GUEST_SHA256}))
    monkeypatch.setattr(installer, 'ROOT', project)
    monkeypatch.setattr(sys, 'argv', ['generate_runtime.py', '--source-module', str(module), '--output', str(output)])
    monkeypatch.setattr(installer.subprocess, 'check_output', lambda *a, **k: str(tmp_path/'go')+'\n')
    commands = []
    monkeypatch.setattr(installer.subprocess, 'run', lambda args, **kwargs: commands.append(args))
    installer.main()
    assert len(commands) == 1 and commands[0][1] == '-w'  # gofmt only, never a build
    installed = json.loads((output/'provenance.json').read_text())['files_sha256']
    assert not handwritten & set(installed)  # remains handwritten, not translated provenance
    actual = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    assert actual == handwritten | set(installed) | {'provenance.json'}
    for name in handwritten:
        assert (output/name).read_bytes() == (canonical/name).read_bytes()


def test_repository_inventory_matches_committed_provenance():
    # Synthetic negative cases cannot detect an edited real generated file.
    verifier.main()


def test_generated_edit_reports_the_file_and_does_not_bless_it(canonical):
    (canonical/'internal/generatedgo/entry.go').write_text('changed')
    with pytest.raises(ValueError, match='entry.go.*canonical generator/adapter'):
        verifier.main()


def test_generated_source_cannot_be_hidden_as_handwritten(canonical, monkeypatch):
    monkeypatch.setattr(verifier, 'HANDWRITTEN_FILES', ('entry.go',))
    with pytest.raises(ValueError, match='ownership overlaps'):
        verifier.main()


def test_pinned_driver_adapter_contains_snapshot_attribution():
    import hashlib
    spec = importlib.util.spec_from_file_location('driver_installer', ROOT/'scripts/generate_runtime.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    raw = (ROOT/'tests/fixtures/generated-driver.go.txt').read_bytes()
    pins = json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    assert hashlib.sha256(raw).hexdigest() == pins['candidate_files_sha256']['main.go']
    adapted = installer.adapt_driver(raw.decode().replace(installer.OLD, installer.NEW))
    canonical = (ROOT/'internal/generatedgo/main.go').read_text()
    # Compare the changed export boundary before gofmt, without a Go prerequisite
    # for Python-only checks. Exact whole-driver pinned-gofmt bytes are recorded
    # in repair evidence; existing memory glue also has gofmt-normalized semicolons.
    def export_body(text):
        return text[text.index('func exportTransfer('):text.index('func verifyCompiledGuest(')]
    assert ''.join(export_body(adapted).split()) == ''.join(export_body(canonical).split())
    assert '"context"' in adapted and '"github.com/masahitojp/mariamem/internal/timing"' in adapted
    assert 'rc := h.WasiStubs.Fd_dup(m, l0, l1)' in adapted
    assert 'panic("unimplemented WASIX: Fd_dup")' not in adapted
    with pytest.raises(ValueError, match='driver fragment changed'):
        installer.adapt_driver(raw.decode().replace('return os.WriteFile(dst, b, 0600)', 'return nil'))

@pytest.mark.parametrize('family', ['narrow_load', 'narrow_write'])
@pytest.mark.parametrize('change', ['output', 'owner', 'missing'])
def test_template_owned_primitive_rejects_drift(canonical, change, family):
    owner = canonical/f'scripts/runtime_correctness/{family}_darwin_arm64.s.txt'
    output = canonical/f'internal/generatedgo/code/base/{family}_darwin_arm64.s'
    if change == 'output': output.write_text('changed')
    elif change == 'owner': owner.write_text('changed')
    else: owner.unlink()
    with pytest.raises(ValueError, match='template-owned'):
        verifier.main()


def go_inventory_tokens(source):
    """Lexical inventory only: comments/literals cannot manufacture Go calls."""
    import re
    token = re.compile(r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\\n])*"|'
                       r"'(?:\\.|[^'\\\n])*'|`[^`]*`|[^\W\d]\w*|.", re.DOTALL)
    result = []
    for match in token.finditer(source):
        value = match.group()
        if value.isspace() or value.startswith(('//', '/*')):
            continue
        assert value not in ('"', "'", '`'), 'unterminated Go literal in inventory'
        result.append(value)
    return result


def go_inventory_group(tokens, start):
    pairs = {'(': ')', '[': ']', '{': '}'}
    stack = []
    for index in range(start, len(tokens)):
        value = tokens[index]
        if value in pairs:
            stack.append(pairs[value])
        elif value in pairs.values():
            assert stack and value == stack.pop(), 'unbalanced Go inventory group'
            if not stack:
                return index
    raise AssertionError('unterminated Go inventory group')


def go_host_method_bodies(tokens):
    """Find concrete host receiver declarations, without compiling the guest."""
    import re
    index = 0
    while index + 1 < len(tokens):
        if tokens[index:index + 2] != ['func', '(']:
            index += 1
            continue
        end = go_inventory_group(tokens, index + 1)
        receiver = tokens[index + 2:end]
        # A receiver name is optional; parentheses around its type are legal.
        types = [value for value in receiver if value not in ('(', ')')]
        if types not in (['host'], ['*', 'host']):
            types = types[1:]
        index = end + 1
        if types not in (['host'], ['*', 'host']):
            continue
        if (index + 1 >= len(tokens) or tokens[index] == 'func'
                or not re.fullmatch(r'[^\W\d]\w*', tokens[index]) or tokens[index + 1] != '('):
            continue  # A function literal parameter, not a receiver declaration.
        name = tokens[index]
        index = go_inventory_group(tokens, index + 1) + 1
        # Skip result types, including parenthesized results and inline types.
        while index < len(tokens) and tokens[index] != '{':
            if tokens[index] in ('(', '['):
                index = go_inventory_group(tokens, index) + 1
            elif tokens[index] in ('struct', 'interface') and tokens[index + 1:index + 2] == ['{']:
                index = go_inventory_group(tokens, index + 1) + 1
            else:
                index += 1
        assert index < len(tokens), 'missing host method body'
        end = go_inventory_group(tokens, index)
        yield name, tokens[index + 1:end]
        index = end + 1


def go_direct_panic_arguments(body):
    """Include nested bodies and parenthesized calls; exclude selectors."""
    arguments = []
    type_end = -1
    for index, value in enumerate(body):
        if value == 'interface' and body[index + 1:index + 2] == ['{']:
            type_end = go_inventory_group(body, index + 1)
        if index <= type_end:
            continue  # Interface method signatures are not calls.
        if value != 'panic' or (index and body[index - 1] == '.'):
            continue
        left, right = index - 1, index + 1
        while left >= 0 and right < len(body) and body[left] == '(' and body[right] == ')':
            left, right = left - 1, right + 1
        if right < len(body) and body[right] == '(':
            end = go_inventory_group(body, right)
            arguments.append(tuple(body[right + 1:end]))
    return arguments


def validate_wasix_stub_classification(driver, classification):
    """Changes to the actual generated panic boundary require a classification diff."""
    import re
    assert classification.get('schema') == 1
    assert isinstance(classification.get('classification'), str) and classification['classification'].strip()
    declared = classification.get('stubs')
    assert isinstance(declared, dict) and declared
    assert all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) and disposition == 'fail-closed'
               for name, disposition in declared.items())
    guards = classification.get('guard_panics', {})
    assert isinstance(guards, dict) and not set(guards) & set(declared)
    assert all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) and isinstance(expressions, list)
               and expressions and all(isinstance(expr, str) and expr.strip() for expr in expressions)
               for name, expressions in guards.items()), 'invalid host panic guard classification'
    observed_guards, observed_stubs = {}, []
    for name, body in go_host_method_bodies(go_inventory_tokens(driver)):
        calls = go_direct_panic_arguments(body)
        if name in declared:
            assert len(calls) == 1, 'unclassified direct host panic: ' + name
            assert calls[0] in [(f'"unimplemented WASIX: {name}"',),
                                (f'`unimplemented WASIX: {name}`',)], 'noncanonical WASIX stub: ' + name
            assert body == ['panic', '(', *calls[0], ')'] or body == ['panic', '(', *calls[0], ')', ';'], 'noncanonical WASIX stub: ' + name
            observed_stubs.append(name)
        elif calls:
            assert name in guards and name not in observed_guards, 'unclassified direct host panic: ' + name
            observed_guards[name] = calls
    expected_guards = {name: [tuple(go_inventory_tokens(expr)) for expr in expressions]
                       for name, expressions in guards.items()}
    assert observed_guards == expected_guards, 'host panic guard classification differs from driver'
    assert len(observed_stubs) == len(set(observed_stubs)), 'duplicate WASIX stub'
    assert set(observed_stubs) == set(declared), 'WASIX stub classification differs from driver'


def test_generated_driver_wasix_stubs_are_explicitly_classified():
    # Host methods can be added in any non-test file in the generatedgo package.
    sources = sorted(path for path in (ROOT/'internal/generatedgo').glob('*.go')
                     if not path.name.endswith('_test.go'))
    assert sources
    validate_wasix_stub_classification(
        '\n'.join(path.read_text() for path in sources),
        json.loads((ROOT/'release/wasix-host-stubs.json').read_text()))


@pytest.mark.parametrize('mutation', ['addition', 'removed', 'duplicate', 'malformed', 'unclassified', 'other_panic', 'typed_panic', 'wrong_method'])
def test_wasix_stub_inventory_rejects_unreviewed_changes(mutation):
    source = 'func (h *host) Fd_dup2() { panic("unimplemented WASIX: Fd_dup2") }\n'
    contract = {'schema': 1, 'classification': 'fail-closed', 'stubs': {'Fd_dup2': 'fail-closed'}}
    if mutation == 'addition':
        source += 'func (h *host) New_import() { panic("unimplemented WASIX: New_import") }\n'
    elif mutation == 'removed':
        source = ''
    elif mutation == 'duplicate':
        source += source
    elif mutation == 'malformed':
        source = source.replace('panic("unimplemented WASIX: Fd_dup2")', 'panic("unimplemented WASIX: "+"Fd_dup2")')
    elif mutation == 'other_panic':
        source += 'func (h *host) New_import() { panic("not implemented") }\n'
    elif mutation == 'typed_panic':
        source += 'func (h *host) New_import() int64 { panic("not implemented") }\n'
    elif mutation == 'wrong_method':
        source = source.replace('host) Fd_dup2(', 'host) Different(')
    else:
        contract['stubs']['Fd_dup2'] = ''
    with pytest.raises(AssertionError):
        validate_wasix_stub_classification(source, contract)


@pytest.mark.parametrize('body', [
    '_ = h; panic("not implemented")',
    '_ = h\n panic("not implemented")',
    'if h != nil { panic("not implemented") }',
    'switch { default: panic("not implemented") }',
    'for { panic("not implemented") }',
    'defer func() { panic("not implemented") }()',
    'panic /* comment */ ("not implemented")',
    '(panic)("not implemented")',
    '((panic))("not implemented")',
])
def test_wasix_stub_inventory_rejects_hidden_direct_panic(body):
    source = ('func (h *host) Fd_dup2() { panic("unimplemented WASIX: Fd_dup2") }\n'
              'func (h *host) New_import() { ' + body + ' }\n')
    contract = {'schema': 1, 'classification': 'fail-closed',
                'stubs': {'Fd_dup2': 'fail-closed'}}
    with pytest.raises(AssertionError, match='unclassified direct host panic'):
        validate_wasix_stub_classification(source, contract)


@pytest.mark.parametrize('extra', [
    'func (h *host) Implemented() { _ = h; return }',
    'func (h *host) Implemented() { /* } panic("fake") { */ _ = h }',
    'func (h *host) Implemented() { // panic("fake") }\n _ = h }',
    'func (h *host) Implemented() { _ = "} panic(\\\"fake\\\") {"; _ = \'}\' }',
    'func (h *host) Implemented() { _ = `func (h *host) Fake() { panic("fake") }` }',
    'func (h *host) Implemented() { /* panic("unimplemented WASIX: Fake") */ _ = h }',
    'func (h *host) Implemented() { _ = `func (h *host) Fake() { panic("unimplemented WASIX: Fake") }` }',
    'func (h *host) Implemented() { h.panic("selector"); (h.panic)("selector") }',
    'func (h *host) Implemented() { var value struct { panic func() }; _ = value }',
    'func (h *host) Implemented() { var value interface { panic() }; _ = value }',
    'func Other() { panic("outside host") }',
    'func (host *other) Other() { panic("other receiver") }',
    'var callback = func(h *host) func() { return func() { panic("outside host") } }',
])
def test_wasix_stub_inventory_ignores_non_calls_and_non_host_methods(extra):
    source = 'func (h *host) Fd_dup2() { panic("unimplemented WASIX: Fd_dup2") }\n'
    contract = {'schema': 1, 'classification': 'fail-closed', 'stubs': {'Fd_dup2': 'fail-closed'}}
    validate_wasix_stub_classification(source + extra, contract)


@pytest.mark.parametrize('signature', [
    '(h host) New_import()',
    '(h (*host)) New_import() int64',
    '(h *host) New_import() (out struct { Field int64 })',
    '(h *host) New_import() struct { Field int64 }',
    '(h /* receiver */ *host) New_import() interface { Method() }',
])
def test_wasix_stub_inventory_checks_receiver_and_result_variants(signature):
    source = ('func (h *host) Fd_dup2() { panic("unimplemented WASIX: Fd_dup2") }\n'
              'func ' + signature + ' { if true { panic("not implemented") } }')
    contract = {'schema': 1, 'classification': 'fail-closed', 'stubs': {'Fd_dup2': 'fail-closed'}}
    with pytest.raises(AssertionError, match='unclassified direct host panic'):
        validate_wasix_stub_classification(source, contract)


@pytest.mark.parametrize('mutation', ['none', 'removed', 'changed', 'extra', 'new_method', 'malformed'])
def test_wasix_stub_inventory_pins_existing_guard_calls(mutation):
    source = ('func (h *host) Fd_dup2() { panic("unimplemented WASIX: Fd_dup2") }\n'
              'func (h *host) Checked() { if h == nil { panic("invalid input") }; use(h) }')
    contract = {'schema': 1, 'classification': 'fail-closed', 'stubs': {'Fd_dup2': 'fail-closed'},
                'guard_panics': {'Checked': ['"invalid input"']}}
    if mutation == 'none':
        validate_wasix_stub_classification(source, contract)
        return
    if mutation == 'removed':
        source = source.replace('panic("invalid input")', 'return')
    elif mutation == 'changed':
        source = source.replace('invalid input', 'not implemented')
    elif mutation == 'extra':
        source = source.replace('use(h)', 'panic("invalid input")')
    elif mutation == 'new_method':
        source += '\nfunc (h *host) Other() { panic("invalid input") }'
    else:
        contract['guard_panics']['Checked'] = ['']
    with pytest.raises(AssertionError):
        validate_wasix_stub_classification(source, contract)


def test_wasix_stub_inventory_cannot_classify_a_commented_declaration():
    source = '// func (h *host) Fd_dup2() { panic("unimplemented WASIX: Fd_dup2") }\n'
    contract = {'schema': 1, 'classification': 'fail-closed', 'stubs': {'Fd_dup2': 'fail-closed'}}
    with pytest.raises(AssertionError, match='classification differs'):
        validate_wasix_stub_classification(source, contract)
