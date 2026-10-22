"""Isolated CI runner prerequisites for the extra official-driver replay."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

URL = 'https://files.pythonhosted.org/packages/c4/ba/cedef19833be88e07bfff11964441cda8a998f1628dd3b2fa3e7751d36e0/mariadb-1.1.14.tar.gz#sha256=e6d702a53eccf20922e47f2f45cfb5c7a0c2c6c0a46e4ee2d8a80d0ff4a52f34'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    r = {'scope': 'CI runner only; no product dependency change', 'python': sys.version,
         'driver_sdist': URL, 'result': 'FAIL'}
    env = dict(os.environ)
    try:
        if platform.system() == 'Darwin':
            # Do not select a different driver or patch SSL to make it import.
            env['HOMEBREW_NO_AUTO_UPDATE'] = '1'
            subprocess.run(['brew', 'install', 'mariadb-connector-c'], env=env, check=True)
            prefix = subprocess.check_output(['brew', '--prefix', 'mariadb-connector-c'], env=env, text=True).strip()
            config = str(Path(prefix) / 'bin/mariadb_config')
        elif platform.system() == 'Linux':
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', '--no-install-recommends', 'libmariadb-dev'], check=True)
            config = '/usr/bin/mariadb_config'
        else:
            raise RuntimeError('unsupported replay runner')
        env['MARIADB_CONFIG'] = config
        r['connector_c'] = subprocess.check_output([config, '--cc_version'], env=env, text=True).strip()
        subprocess.run([sys.executable, '-m', 'pip', 'install', URL], env=env, check=True)
        r['result'] = 'PASS'
    except Exception as e:
        r['error'] = repr(e)
        raise
    finally:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(r, indent=2) + '\n')


if __name__ == '__main__':
    main()
