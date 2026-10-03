"""Installed host-only wheel checks; copied outside checkout on both platforms."""
import json
from pathlib import Path
import platform
import struct

import mariamem
import pymysql
import pytest


def test_installed_host_contract():
    native = Path(mariamem.__file__).parent / '_native'
    assert {p.name for p in native.iterdir()} == {'manifest.json', 'mariamem-host'}
    manifest = json.loads((native / 'manifest.json').read_text())
    assert manifest['runtime_kind'] == 'generated-go'
    with (native / 'mariamem-host').open('rb') as stream:
        header = stream.read(20)
    if platform.system() == 'Linux':
        assert manifest['platform'] == 'ubuntu24.04-x86_64'
        assert (manifest['distribution'], manifest['version_id'], manifest['architecture']) == ('ubuntu', '24.04', 'x86_64')
        assert header[:6] == b'\x7fELF\x02\x01'
        assert struct.unpack_from('<H', header, 18)[0] == 62
    else:
        assert manifest['platform'] == 'darwin-arm64' and manifest['minimum_macos'] == 15
        assert struct.unpack_from('<II', header)[0:2] == (0xfeedfacf, 0x100000c)


def test_missing_host_rejected_and_next_start_works(tmp_path):
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start(host_binary=tmp_path / 'missing-host')
    assert failure.value.code == 'native_unavailable'
    assert failure.value.stage == 'artifact_validation'
    with mariamem.start() as db:
        with pymysql.connect(**db.connection_info(), autocommit=True) as a, pymysql.connect(**db.connection_info(), autocommit=True) as b:
            with a.cursor() as cursor:
                cursor.execute('SET @release_session=123')
            with b.cursor() as cursor:
                cursor.execute('SELECT @release_session')
                assert cursor.fetchone() == (None,)
        db.wait_disconnected()
        with pymysql.connect(**db.connection_info()) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT @release_session, 1')
                assert cursor.fetchone() == (None, 1)
        temporary = db.log_path.parent
    db.close()
    assert db.closed and not temporary.exists()
