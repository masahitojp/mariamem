"""Installed Windows wheel acceptance for the changed OS boundaries."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import sysconfig

import mariamem
import pymysql
import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='installed native Windows wheel')


def sql(db, statement):
    with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall()


def test_windows_installed_identity():
    assert Path(mariamem.__file__).is_relative_to(Path(sys.prefix))
    root = Path(mariamem.__file__).parent / '_native'
    assert {p.name for p in root.iterdir()} == {'manifest.json', 'mariamem-host.exe'}
    manifest = json.loads((root / 'manifest.json').read_text())
    arm = sysconfig.get_platform() == 'win-arm64'
    assert manifest['platform'] == ('windows-arm64' if arm else 'windows-x86_64')
    assert manifest['architecture'] == ('arm64' if arm else 'x86_64')
    assert manifest['minimum_windows_build'] == 22000 <= sys.getwindowsversion().build
    binary = root / 'mariamem-host.exe'
    assert hashlib.sha256(binary.read_bytes()).hexdigest() == manifest['sha256'][binary.name]
    with binary.open('rb') as stream:
        dos = stream.read(64)
        assert dos[:2] == b'MZ'
        stream.seek(struct.unpack_from('<I', dos, 60)[0])
        header = stream.read(26)
    assert header[:4] == b'PE\0\0'
    assert struct.unpack_from('<H', header, 4)[0] == (0xAA64 if arm else 0x8664)
    assert struct.unpack_from('<H', header, 24)[0] == 0x20B


def test_windows_close_reaps_host_and_files():
    db = mariamem.start()
    session = db._session
    root = session.root
    try:
        assert sql(db, 'SELECT 1') == ((1,),)
    finally:
        db.close()
        db.close()
    assert session._process.wait(timeout=5) == 0
    assert not root.exists()


def test_windows_host_failure_is_reaped():
    db = mariamem.start()
    session = db._session
    root = session.root
    session._process.kill()
    session._process.wait(timeout=5)
    try:
        with pytest.raises(mariamem.HostError):
            db.status()
    finally:
        db.close()
    assert session._process.poll() is not None
    assert not root.exists()


def test_windows_remote_handoff_and_capacity(tmp_path):
    binary = Path(mariamem.__file__).parent / '_native/mariamem-host.exe'
    alternate = tmp_path / 'alternate-host.exe'
    shutil.copyfile(binary, alternate)
    with mariamem.start() as db:
        sql(db, 'CREATE TABLE remote_items(id INT) ENGINE=InnoDB')
        db.wait_disconnected()
        with db.snapshot(max_forks=1) as saved:
            with saved.fork(host_binary=alternate) as remote:
                sql(remote, 'INSERT INTO remote_items VALUES(1)')
                assert sql(remote, 'SELECT COUNT(*) FROM remote_items') == ((1,),)
                with pytest.raises(mariamem.HostError) as blocked:
                    saved.fork(timeout=.05)
                assert blocked.value.code == 'pool_timeout'
            with saved.fork(timeout=5) as local:
                assert sql(local, 'SELECT COUNT(*) FROM remote_items') == ((0,),)


def test_windows_prepare_seeds_snapshot(tmp_path):
    from mariamem._prepare import _run_command
    command = mariamem.PrepareCommand([sys.executable, '-c', '''import json,os,pymysql
with pymysql.connect(**json.loads(os.environ['MARIAMEM_PREPARE_CONNECTION_INFO']),autocommit=True) as conn:
    with conn.cursor() as cursor:
        cursor.execute('CREATE TABLE prepared_items(id INT) ENGINE=InnoDB')
        cursor.execute('INSERT INTO prepared_items VALUES(7)')
'''])
    with mariamem.start() as db:
        result = _run_command(command, db, tmp_path)
        assert result.process_cleanup == 'completed'
        db.wait_disconnected()
        with db.snapshot() as saved:
            assert 1 <= saved.max_forks <= (1 << 31) - 1
            with saved.fork() as child:
                assert sql(child, 'SELECT id FROM prepared_items') == ((7,),)
