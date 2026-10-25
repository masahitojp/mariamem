"""Acquire the pinned OS-specific native bottle in disposable CI scratch."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

from bind_input import HERE
from linux_acquisition import require, source_identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--expected-source-commit', required=True)
    args = parser.parse_args()
    source_identity(args.expected_source_commit)
    require(platform.system() == 'Darwin' and platform.machine() == 'arm64', 'native Mac arm64 required')
    key = {'15': 'arm64_sequoia', '26': 'arm64_tahoe', '27': 'arm64_golden_gate'}.get(platform.mac_ver()[0].split('.')[0])
    require(key is not None, 'no pinned bottle for this macOS version')
    root = args.workspace.resolve()
    (root/'temp').mkdir(parents=True, exist_ok=True)
    (root/'evidence').mkdir(exist_ok=True)
    formula = HERE/'input/macos/homebrew-formula.json'
    pin = json.loads(formula.read_text())['bottle']['stable']['files'][key]
    bottle = root/'temp'/('mariadb-12.3.3.'+key+'.bottle.tar.gz')
    subprocess.run(['curl', '-fL', '--max-time', '180', '--header', 'Authorization: Bearer QQ==',
                    '--output', str(bottle), pin['url']], check=True)
    subprocess.run([sys.executable, str(HERE/'preflight_macos.py'), '--workspace', str(root),
                    '--bottle-key', key, '--formula-json', str(formula),
                    '--formula-source', str(HERE/'input/macos/mariadb@12.3.rb')], check=True)
    report = json.loads((root/'evidence/macos-preflight.json').read_text())
    require(report['result'] == 'PASS' and report['source_commit'] == args.expected_source_commit,
            'Mac acquisition/source did not pass')


if __name__ == '__main__':
    main()
