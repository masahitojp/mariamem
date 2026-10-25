"""Ordered test-only comparison on one native OS and two supported Pythons."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tempfile
import shutil

from bind_input import HERE, ROOT, bind, check_binding
from linux_acquisition import require, source_identity
from oracles import check_expected, connect, differences, observe
from native_errors import ImportFailure
from routes import empty_schema, load

LINUX_IMAGE = 'mariadb@sha256:2f4f46f80e7251990bfdc601ae3f7f2964ddb4dc1868f7deca699fc1ece8c35e'


@contextmanager
def mac_native(acquisition, evidence):
    receipt = json.loads((acquisition/'evidence/macos-preflight.json').read_text())
    require(receipt['result'] == 'PASS', 'Mac native acquisition failed')
    command = receipt['server_command']
    socket = Path(next(a.split('=', 1)[1] for a in command if a.startswith('--socket=')))
    port = int(next(a.split('=', 1)[1] for a in command if a.startswith('--port=')))
    with (evidence/'macos-native-server.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            deadline = time.monotonic()+40
            while not socket.exists():
                require(process.poll() is None and time.monotonic() < deadline, 'Mac native server startup failed')
                time.sleep(.2)
            binary = acquisition/'temp/macos-native/mariadb@12.3/12.3.3_1/bin/mariadb'
            require(hashlib.sha256(binary.read_bytes()).hexdigest() == receipt['executables']['mariadb']['sha256'],
                    'Mac client changed after acquisition')
            yield [str(binary)], port
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            (evidence/'macos-server-cleanup.json').write_text(json.dumps({'server_reaped': process.poll() is not None})+'\n')


def route_probe(host, route, command, reference, output):
    import mariamem
    output.mkdir()
    report = dict(result='FAIL', route=route, stage='start', snapshot_attempted=False)
    db = None
    try:
        with mariamem.start(host_binary=str(host)) as db:
            info = db.connection_info()
            report['stage'] = 'import'
            empty_schema(info)
            report['import'] = load(info, route, 'success', command, output, db=db)
            report['stage'] = 'comparison'
            with connect(info) as connection:
                actual = observe(connection)
            (output/'observations.json').write_text(json.dumps(actual, indent=2, ensure_ascii=False)+'\n')
            check_expected(actual)
            changed = differences(reference['observation'], actual)
            require(not changed, 'native reference differences: '+','.join(changed))
            report.update(result='PASS', stage='complete')
    except Exception as error:
        report['error'] = error.details if isinstance(error, ImportFailure) else str(error)
    finally:
        if db is not None:
            report['cleanup'] = dict(closed=db.closed,
                host_reaped=db._session._process.poll() is not None,
                directory_removed=not db._session.root.exists())
            if not all(report['cleanup'].values()):
                report['result'] = 'FAIL'
        (output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def execute(args, command, reference_path, evidence, temp):
    from git_identity import verify_go_binary
    reference = json.loads(reference_path.read_text())
    binding = check_binding(evidence/'binding.json', args.expected_source_commit)
    require(reference['result'] == 'PASS' and reference['source_commit'] == args.expected_source_commit
            and reference['binding'] == binding, 'native reference source/binding mismatch')
    import mariamem
    package = Path(mariamem.__file__).resolve().parent
    require(not package.is_relative_to(ROOT/'python'), 'source-tree SDK shadowed installed product')
    host = package/'_native/mariamem-host'
    manifest = json.loads((package/'_native/manifest.json').read_text())
    require(hashlib.sha256(host.read_bytes()).hexdigest() == manifest['sha256']['mariamem-host'],
            'installed wheel host hash mismatch')
    (temp/'os-tmp').mkdir()
    env = dict(os.environ, GOTOOLCHAIN='go1.26.10',
        TMPDIR=str(temp/'os-tmp'), PYTHONPATH=str(HERE), PYTHONDONTWRITEBYTECODE='1')
    os.environ['TMPDIR'] = str(temp/'os-tmp')
    tempfile.tempdir = str(temp/'os-tmp')
    source_identity(args.expected_source_commit)
    buildinfo = verify_go_binary(ROOT, host, args.expected_source_commit)
    summary = dict(result='FAIL', source_commit=args.expected_source_commit, binding=binding,
                   platform=platform.platform(), host_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),
                   host_buildinfo=buildinfo, ordered_route_probes={}, interpreter_runs={})
    # Probe both imports independently, in order, before any Snapshot/child run.
    import mariamem
    require(not Path(mariamem.__file__).resolve().is_relative_to(ROOT/'python'), 'source-tree SDK shadowed installed product')
    for route in ['native', 'reader']:
        summary['ordered_route_probes'][route] = route_probe(host, route, command, reference, evidence/('probe-'+route))
    try:
        for label, python, version in [('py311', args.minimum_python, (3, 11)), ('py314', args.current_python, (3, 14))]:
            actual_version = json.loads(subprocess.check_output([str(python), '-c',
                'import sys,json;print(json.dumps(list(sys.version_info[:2])))'], text=True))
            require(tuple(actual_version) == version, 'wrong interpreter for '+label)
            output = evidence/label
            argv = [str(python), str(HERE/'run.py'), '--host', str(host), '--host-source', args.expected_source_commit,
                    '--binding', str(evidence/'binding.json'), '--reference', str(reference_path),
                    '--variant-reference', str(reference_path.parent.parent/'variant/reference.json'),
                    '--client-command', json.dumps(command), '--output', str(output)]
            with (evidence/(label+'.console.txt')).open('w') as log:
                completed = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            result_file = output/'results.json'
            result = json.loads(result_file.read_text()) if result_file.exists() else {'result': 'FAIL', 'reason': 'no result receipt'}
            summary['interpreter_runs'][label] = {'exit_code': completed.returncode, 'result': result['result']}
        if (all(r['result'] == 'PASS' for r in summary['ordered_route_probes'].values())
                and all(r['result'] == 'PASS' and r['exit_code'] == 0 for r in summary['interpreter_runs'].values())
                and len(summary['interpreter_runs']) == 2):
            summary['result'] = 'PASS'
    finally:
        (evidence/'campaign.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary['result'] == 'PASS'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--minimum-python', type=Path, required=True)
    parser.add_argument('--current-python', type=Path, required=True)
    parser.add_argument('--macos-acquisition', type=Path)
    args = parser.parse_args()
    args.workspace = args.workspace.resolve()
    args.reference = args.reference.resolve()
    evidence, temp = args.workspace/'evidence', args.workspace/'temp'
    evidence.mkdir(parents=True)
    temp.mkdir()
    producer = args.reference.parent.parent/'candidate-producer'
    shutil.copytree(producer, evidence/'candidate-producer')
    (evidence/'binding.json').write_text(json.dumps(bind(args.expected_source_commit, evidence/'candidate-producer'), indent=2)+'\n')
    if args.macos_acquisition:
        with mac_native(args.macos_acquisition.resolve(), evidence) as (command, port):
            native_out = evidence/'macos-reference'
            subprocess.run([sys.executable, str(HERE/'native_reference.py'), '--port', str(port),
                '--expected-source-commit', args.expected_source_commit, '--binding', str(evidence/'binding.json'),
                '--client-command', json.dumps(command), '--output', str(native_out)], check=True)
            mac_reference = json.loads((native_out/'reference.json').read_text())
            ubuntu_reference = json.loads(args.reference.read_text())
            require(mac_reference['observation'] == ubuntu_reference['observation'], 'native macOS/Ubuntu reference difference')
            passed = execute(args, command, args.reference, evidence, temp)
    else:
        require(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'native Ubuntu x86_64 required')
        subprocess.run(['docker', 'pull', LINUX_IMAGE], check=True)
        pin = json.loads((HERE/'linux-native-pin.json').read_text())
        binary = subprocess.check_output(['docker', 'run', '--rm', '--entrypoint=cat', LINUX_IMAGE, '/usr/bin/mariadb'])
        require(hashlib.sha256(binary).hexdigest() == pin['programs']['mariadb']['sha256'], 'Linux native client changed')
        command = ['docker', 'run', '--rm', '-i', '--network=host', '--entrypoint=mariadb', LINUX_IMAGE]
        passed = execute(args, command, args.reference, evidence, temp)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
