"""Exact native acquisition assertions; never generates or imports a dump."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = Path(__file__).with_name('linux-native-pin.json')
sys.path.insert(0, str(ROOT/'scripts'))
from git_identity import inspect_ref, require_commit


def require(condition, reason):
    # Do not use Python assert: python -O must not turn off input guards.
    if not condition:
        raise ValueError(reason)


def architecture(binary):
    require(len(binary) >= 20 and binary[:4] == b'\x7fELF', 'not an ELF executable')
    require(binary[4] in (1, 2) and binary[5] in (1, 2), 'invalid ELF encoding')
    order = '<' if binary[5] == 1 else '>'
    return {'format': 'ELF', 'bits': {1: 32, 2: 64}[binary[4]],
            'byte_order': 'little' if binary[5] == 1 else 'big',
            'machine': struct.unpack_from(order+'H', binary, 18)[0]}


def source_identity(expected):
    require_commit(ROOT, expected)
    actual = asdict(inspect_ref(ROOT, 'HEAD'))
    require(actual['object_type'] == 'commit' and actual['source_commit'] == expected,
            'checkout source_commit differs from requested source SHA')
    require(not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip(),
            'checkout is dirty')
    return actual


def validate(observed, pin, expected_source):
    require(isinstance(expected_source, str) and re.fullmatch('[0-9a-f]{40}', expected_source),
            'expected source must be a full commit SHA')
    source = observed.get('source', {})
    require(source.get('object_type') == 'commit' and
            source.get('object_sha') == source.get('source_commit') == expected_source,
            'source identity mismatch')
    for key in ['host', 'image_ref', 'image', 'startup_query']:
        require(observed.get(key) == pin[key], key+' mismatch')
    require(observed.get('container_image') == pin['image']['id'], 'container image mismatch')
    programs = observed.get('programs', {})
    require(set(programs) == set(pin['programs']), 'program inventory mismatch')
    for name, expected in pin['programs'].items():
        require(programs[name] == expected, name+' identity mismatch')


def capture(container, expected_source, pin, output):
    observed = {'source': source_identity(expected_source),
                'host': {'system': platform.system(), 'machine': platform.machine()},
                'image_ref': pin['image_ref'], 'programs': {}}
    # Resolve source before spending work on container/executable inspection.
    def command(arguments):
        result = subprocess.run(arguments, capture_output=True, check=True, timeout=45)
        return result.stdout
    image_raw = command(['docker', 'image', 'inspect', pin['image_ref']])
    container_raw = command(['docker', 'inspect', container])
    (output/'image.json').write_bytes(image_raw)
    (output/'container.json').write_bytes(container_raw)
    image = json.loads(image_raw)[0]
    require(pin['image_ref'] in image['RepoDigests'], 'inspected image does not bind pinned manifest')
    observed['image'] = {'id': image['Id'], 'os': image['Os'], 'architecture': image['Architecture']}
    observed['container_image'] = json.loads(container_raw)[0]['Image']
    for name, expected in pin['programs'].items():
        resolved = command(['docker', 'exec', container, 'sh', '-ec', 'command -v "$1"', 'sh', name]).decode().strip()
        require(resolved == expected['path'], name+' PATH resolves to another executable')
        binary = command(['docker', 'exec', container, 'cat', resolved])
        version = command(['docker', 'exec', container, name, '--no-defaults', '--version'])
        (output/(name+'-version.txt')).write_bytes(version)
        observed['programs'][name] = {'path': resolved, 'sha256': hashlib.sha256(binary).hexdigest(),
                                      'version': version.decode().rstrip('\n'),
                                      'architecture': architecture(binary)}
    help_text = command(['docker', 'exec', container, 'mariadb-dump', '--no-defaults', '--help'])
    (output/'dump-help.txt').write_bytes(help_text)
    query = ("SELECT VERSION(), @@version_compile_machine; "
             "SELECT user,host FROM mysql.user WHERE user='root' AND host='localhost'; SELECT 1;")
    startup = command(['docker', 'exec', container, 'mariadb', '--no-defaults', '--user=root',
                       '--batch', '--skip-column-names', '--execute='+query])
    (output/'startup-query.txt').write_bytes(startup)
    observed['startup_query'] = startup.decode()
    (output/'observed.json').write_text(json.dumps(observed, indent=2)+'\n')
    validate(observed, pin, expected_source)
    # Reject source changes made during acquisition as well as before it.
    require(source_identity(expected_source) == observed['source'], 'source changed during acquisition')
    return observed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--expected-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    require(not (args.output/'result.json').exists(), 'refuse stale result receipt')
    result = {'result': 'FAIL', 'scope': 'native acquisition only on observed host',
              'dump_generated': False, 'reader_executed': False}
    try:
        pin = json.loads(PIN.read_text())
        observed = capture(args.container, args.expected_source_commit, pin, args.output)
        result.update(result='PASS', source_commit=observed['source']['source_commit'],
                      pin_sha256=hashlib.sha256(PIN.read_bytes()).hexdigest())
    except Exception as error:
        result['error'] = str(error)
    finally:
        (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
