"""Installed-wheel-only Ubuntu product regression; copied outside checkout."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import mariamem
import pymysql
import pytest


def test_multi_client_session_reuse():
    with mariamem.start() as db:
        with pymysql.connect(**db.connection_info(), autocommit=True) as a, pymysql.connect(**db.connection_info(), autocommit=True) as b:
            with a.cursor() as cursor:
                cursor.execute('SET @ubuntu_test=123')
            with b.cursor() as cursor:
                cursor.execute('SELECT @ubuntu_test')
                assert cursor.fetchone() == (None,)
                cursor.execute('SELECT 1')
                assert cursor.fetchone() == (1,)
        db.wait_disconnected()
        with pymysql.connect(**db.connection_info()) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT @ubuntu_test')
                assert cursor.fetchone() == (None,)


def test_timeout_and_cleanup():
    db = mariamem.start(query_timeout=1)
    temporary = db.log_path.parent
    pid = db.diagnostics['runtime_pid']
    try:
        with pymysql.connect(**db.connection_info(),read_timeout=5) as connection:
            with connection.cursor() as cursor:
                with pytest.raises(pymysql.Error,match='database instance terminated'):
                    cursor.execute('SELECT SLEEP(10)')
        deadline = time.monotonic()+5
        while not db.closed and time.monotonic()<deadline:
            time.sleep(.01)
        with pytest.raises(mariamem.HostError) as failure:
            db.status()
        assert failure.value.code == 'unusable'
        with pytest.raises(mariamem.HostError):
            db.snapshot()
    finally:
        db.close()
        db.close()
    assert not temporary.exists()
    with pytest.raises(ProcessLookupError):
        os.kill(pid,0)


def test_startup_diagnostics(tmp_path,monkeypatch):
    installed = Path(mariamem.__file__).parent / '_native'
    native=tmp_path/'native'
    shutil.copytree(installed,native)
    monkeypatch.setenv('MARIAMEM_NATIVE_DIR',str(native))
    (native/'mariamem.wasmu').write_bytes(b'corrupt')
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code=='artifact_mismatch'
    # Update only this test's manifest to reach the real runtime startup boundary.
    manifest=json.loads((native/'manifest.json').read_text())
    manifest['sha256']['mariamem.wasmu']=hashlib.sha256(b'corrupt').hexdigest()
    sidecar=json.loads((native/'mariamem.wasmu.json').read_text())
    sidecar['module_sha256']=manifest['sha256']['mariamem.wasmu']
    (native/'mariamem.wasmu.json').write_text(json.dumps(sidecar))
    manifest['sha256']['mariamem.wasmu.json']=hashlib.sha256((native/'mariamem.wasmu.json').read_bytes()).hexdigest()
    (native/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(mariamem.HostError) as failure:
        mariamem.start()
    assert failure.value.code in ('guest_start','guest_connection')
    assert failure.value.stage in ('guest_launch','guest_ready')
