"""Exact-source native reference and standard-settings guest comparison."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import ssl
import subprocess
import sys
import uuid
from pathlib import Path

import run as base
import run_mixed as mixed

ROOT, HERE = base.ROOT, base.HERE
sys.path.insert(0, str(ROOT / 'tests/dump_import_acceptance'))
from linux_acquisition import PIN, source_identity, validate


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    manifest = json.loads((HERE / 'input-manifest.json').read_text())
    for name, expected in manifest['application_sha256'].items():
        require(digest(ROOT / name) == expected, 'application input differs: ' + name)
    packages = {name: importlib.metadata.version(name) for name in manifest['versions']}
    require(packages == manifest['versions'], 'package pins differ')
    paths = list(manifest['application_sha256'])
    for directory in [HERE, ROOT / 'docs/examples/django']:
        paths += subprocess.check_output(['git', 'ls-files', str(directory)], cwd=ROOT, text=True).splitlines()
    paths += ['tests/dump_import_acceptance/linux-native-pin.json',
              'tests/dump_import_acceptance/linux_acquisition.py', 'scripts/git_identity.py']
    return dict(packages=packages, sha256={name: digest(ROOT / name) for name in sorted(set(paths))})


def suite_names():
    return ([f'lifecycle-{runner}-{mode}-{reverse}' for runner, mode, reverse in base.CASES]
            + [f'mixed-{runner}-{order}' for runner in ['manage', 'pytest'] for order in mixed.ORDERS])


def check_reference(reference, expected, current_inputs, minor):
    require(reference.get('result') == 'PASS', 'native reference did not pass')
    require(reference.get('source_commit') == expected, 'native source differs')
    require(reference.get('inputs') == current_inputs, 'native inputs differ')
    require(reference.get('python_minor') == minor, 'native Python minor differs')
    require(reference.get('host', {}).get('system') == 'Linux'
            and reference['host'].get('machine') == 'x86_64', 'native host differs')
    validate(reference.get('acquisition', {}), json.loads(PIN.read_text()), expected)
    require(set(reference.get('suites', {})) == set(suite_names()), 'native suite inventory differs')
    require(all(v.get('result') == 'PASS' for v in reference['suites'].values()), 'native suite failed')
    require(set(reference.get('failures', {})) == {'manage', 'pytest'}, 'native failure inventory differs')
    require(all(v.get('result') == 'PASS_FAILURE_DETECTED_BEFORE_TEST_BODY'
                for v in reference['failures'].values()), 'native failure oracle failed')
    require(reference.get('native_schemas_removed') is True, 'native cleanup missing')


def comparable(observation):
    # Preserve raw errors in receipts. Compare stable semantics across host paths
    # and unique schema names; the local oracle checks exact markers/errno first.
    value = json.loads(json.dumps(observation))
    if 'summary' in value:
        value['summary']['failures'] = [entry['name'] for entry in value['summary']['failures']]
    for failure in value.get('setup_failures', []):
        failure['errors'] = [dict(type=entry['type'], errno=entry['args'][0])
                             for entry in failure['errors']]
    return value


def campaign(info, original, target, out, reference=None):
    results = {}
    for runner, mode, reverse in base.CASES:
        name = f'lifecycle-{runner}-{mode}-{reverse}'
        directory = out / name
        observation = base.run_case(info, original, target, runner, mode, reverse, directory, False)
        observation['projection'] = mixed.projection(mixed.events(directory))
        if reference:
            require(comparable(observation) == comparable(reference['suites'][name]), name + ' native observation mismatch')
        results[name] = observation
    for runner in ['manage', 'pytest']:
        for order in mixed.ORDERS:
            name = f'mixed-{runner}-{order}'
            observation = mixed.mixed(info, original, target, runner, order, out / name)
            if reference:
                require(comparable(observation) == comparable(reference['suites'][name]), name + ' native observation mismatch')
            results[name] = observation
    return results


def cleaned(source):
    # Test-only observation of the public owner's completed cleanup, no force cleanup.
    return dict(source_closed=source.closed, host_reaped=source._session._process.poll() is not None,
                temp_removed=not source._session.root.exists())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', required=True, choices=['native', 'guest'])
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--native-port', type=int)
    parser.add_argument('--acquisition', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--host', type=Path)
    args = parser.parse_args()
    source_identity(args.expected_source_commit)
    current_inputs = inputs()
    minor = f'{sys.version_info.major}.{sys.version_info.minor}'
    require(minor in ['3.11', '3.14'], 'unsupported Python input')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(result='FAIL', source_commit=args.expected_source_commit, inputs=current_inputs,
                  python=sys.version, python_minor=minor, openssl=ssl.OPENSSL_VERSION,
                  host=dict(system=platform.system(), machine=platform.machine()), route=args.route,
                  suites={}, failures={}, recipes={})
    token = 'w3ci_' + uuid.uuid4().hex[:10]
    original, target = token, 'test_' + token
    try:
        if args.route == 'native':
            require(args.native_port and args.acquisition, 'native inputs required')
            acquisition = json.loads((args.acquisition / 'observed.json').read_text())
            validate(acquisition, json.loads(PIN.read_text()), args.expected_source_commit)
            acquisition_result = json.loads((args.acquisition / 'result.json').read_text())
            require(acquisition_result.get('result') == 'PASS'
                    and acquisition_result.get('source_commit') == args.expected_source_commit
                    and acquisition_result.get('pin_sha256') == digest(PIN), 'acquisition failed or differs')
            report['acquisition'] = acquisition
            info = dict(host='127.0.0.1', port=args.native_port)
            require(base.query(info, 'SELECT VERSION()')[0][0].startswith('12.3.3-MariaDB'), 'server differs')
            try:
                base.initialize(info, original)
                report['suites'] = campaign(info, original, target, out)
                for runner in ['manage', 'pytest']:
                    try:
                        report['failures'][runner] = mixed.failure(info, original, target, runner, out / ('failure-' + runner))
                    finally:
                        base.query(info, f'DROP DATABASE IF EXISTS `{target}`')
            finally:
                base.query(info, f'DROP DATABASE IF EXISTS `{target}`')
                base.query(info, f'DROP DATABASE IF EXISTS `{original}`')
                report['native_schemas_removed'] = base.schemas(info, original) == base.schemas(info, target) == 0
            require(report['native_schemas_removed'], 'native schemas remain')
        else:
            require(args.host and args.reference, 'guest inputs required')
            reference = json.loads((args.reference / 'result.json').read_text())
            check_reference(reference, args.expected_source_commit, current_inputs, minor)
            report['native_reference_sha256'] = digest(args.reference / 'result.json')
            report['binary_identity'] = base.verify_go_binary(ROOT, args.host.resolve(), args.expected_source_commit)
            import mariamem
            source = mariamem.start(host_binary=args.host.resolve())
            try:
                info = source.connection_info()
                base.initialize(info, original)
                report['suites'] = campaign(info, original, target, out, reference)
            finally:
                source.close()
                report['owner'] = cleaned(source)
            require(all(report['owner'].values()), 'ordinary owner cleanup incomplete')
            # A failed migration always gets a fresh owner, never a Snapshot/reused owner.
            for runner in ['manage', 'pytest']:
                source = mariamem.start(host_binary=args.host.resolve())
                try:
                    info = source.connection_info()
                    base.initialize(info, original)
                    observation = mixed.failure(info, original, target, runner, out / ('failure-' + runner))
                    require(comparable(observation) == comparable(reference['failures'][runner]), runner + ' failure mismatch')
                    report['failures'][runner] = observation
                finally:
                    source.close()
                    report['failure_owner_' + runner] = cleaned(source)
                require(all(report['failure_owner_' + runner].values()), 'failed owner cleanup incomplete')
                for broken in [False, True]:
                    name = runner + ('-broken' if broken else '-normal')
                    report['recipes'][name] = mixed.recipe(runner, broken, args.host.resolve(), out / ('recipe-' + name))
        source_identity(args.expected_source_commit)
        report['result'] = 'PASS'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        base.write(out / 'result.json', report)


if __name__ == '__main__':
    main()
