"""Runtime-independent exact-module and clean supported-platform acceptance helpers."""
import os
from pathlib import Path
import platform
import subprocess
from native_target import DARWIN, UBUNTU
from generated_release import require
MODULE = 'github.com/masahitojp/mariamem'

def verify_resolved_commit(resolved, expected, requested_tag=None):
    """Bind a CI candidate's public Go module to the exact build commit."""
    if resolved.get('Path') != MODULE or not resolved.get('Version') or not resolved.get('Sum'):
        raise ValueError('public module identity/version/checksum is incomplete')
    if requested_tag and resolved.get('Version') != requested_tag:
        raise ValueError('public module version differs from requested release tag')
    origin = resolved.get('Origin') or {}
    actual = origin.get('Hash')
    if actual != expected:
        raise ValueError(f'public module commit mismatch: expected {expected}, resolved {actual or "unknown"}')


def bind_remote_origin(resolved, remote, expected, requested_tag=None):
    """Match proxy-fetched module identity to a direct immutable remote query."""
    if any(remote.get(key) != resolved.get(key) for key in ('Path', 'Version')):
        raise ValueError('direct remote module identity/version differs from fetched module')
    bound = {**resolved, 'Origin': remote.get('Origin') or {}}
    verify_resolved_commit(bound, expected, requested_tag)
    return bound


def isolated_env(work):
    env = {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN') and not k.startswith(('GO', 'MARIAMEM_', 'WASMER_', 'WASIX_', 'DYLD_', 'LD_'))}
    env.update(GOWORK='off', GOENV='off', GOFLAGS='-modcacherw', GOTOOLCHAIN='local', CGO_ENABLED='0',
               GO111MODULE='on', GOPROXY='https://proxy.golang.org,direct', GOSUMDB='sum.golang.org',
               GOPATH=str(work / 'gopath'), GOMODCACHE=str(work / 'modcache'),
               GOCACHE=str(work / 'gocache'), TMPDIR=str(work / 'runtime-tmp'))
    (work / 'runtime-tmp').mkdir()
    return env


def environment(target):
    env = {'system': platform.system(), 'architecture': platform.machine()}
    if target == DARWIN:
        env['product_version'] = subprocess.check_output(['sw_vers', '-productVersion'], text=True).strip()
        require(env['system'] == 'Darwin' and env['architecture'] == 'arm64'
                and int(env['product_version'].split('.')[0]) >= 15, 'smoke requires macOS 15+ arm64')
    else:
        values = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        env.update(distribution=values['ID'].strip('"'), version_id=values['VERSION_ID'].strip('"'))
        require(env['system'] == 'Linux' and env['architecture'] == 'x86_64'
                and env['distribution'] == 'ubuntu' and env['version_id'] == '24.04',
                'smoke requires Ubuntu 24.04 x86_64')
    return env
