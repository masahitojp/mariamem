"""Pinned extraction and startup-helper failure oracles; no network/guest build."""
import base64
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('routine_schema', ROOT/'scripts/routine_schema.py')
schema = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema)


@pytest.fixture
def inputs(tmp_path):
    source, root = tmp_path/'source', tmp_path/'root'
    (source/'scripts').mkdir(parents=True)
    (root/'guest').mkdir(parents=True)
    (root/'release').mkdir()
    # Lossless encoding preserves upstream whitespace and GPL notice; no network fixture.
    raw = base64.decodebytes((ROOT/'tests/fixtures/mariadb-proc-source.sql.base64').read_bytes())
    (source/'scripts/mariadb_system_tables.sql').write_bytes(raw)
    (source/'VERSION').write_text('MYSQL_VERSION_MAJOR=12\nMYSQL_VERSION_MINOR=3\nMYSQL_VERSION_PATCH=3\n')
    for name in ['guest/routine_schema.json', 'release/inputs.lock.json']:
        shutil.copy2(ROOT/name, root/name)
    return source, root


def test_reviewed_native_metadata_matches_pinned_ddl(inputs):
    source, root = inputs
    pin = json.loads((root/'guest/routine_schema.json').read_text())
    result = schema.prepare(source, root=root)
    assert result['ddl_sha256'] == pin['ddl_sha256']
    assert result['header_sha256'] == schema.sha((source/result['header']).read_bytes())
    assert 'GNU General Public License' in (source/result['header']).read_text()
    with pytest.raises(ValueError, match='already exists'):
        schema.prepare(source, root=root)


@pytest.mark.parametrize('field,value', [('source_commit','0'*40),('server_version','13.1.0'),('source_file','other.sql')])
def test_source_identity_mismatch_is_not_accepted(inputs, field, value):
    source, root = inputs
    path=root/'guest/routine_schema.json'; pin=json.loads(path.read_text());pin[field]=value;path.write_text(json.dumps(pin))
    with pytest.raises(ValueError, match='identity mismatch'):
        schema.prepare(source, root=root)


def test_sql_byte_mutation_rejected(inputs):
    source, root=inputs
    p=source/'scripts/mariadb_system_tables.sql';p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError, match='SQL source hash'):
        schema.prepare(source, root=root)


@pytest.mark.parametrize('mutation', ['missing','duplicate','changed'])
def test_source_anchor_and_ddl_are_separately_bound(inputs, mutation):
    source, root=inputs
    p=source/'scripts/mariadb_system_tables.sql';raw=p.read_text()
    ddl=next(l for l in raw.splitlines() if l.startswith('CREATE TABLE IF NOT EXISTS proc ('))
    raw = raw.replace(ddl,'') if mutation=='missing' else raw+'\n'+ddl if mutation=='duplicate' else raw.replace('comment text collate','comment longtext collate')
    p.write_text(raw)
    pinpath=root/'guest/routine_schema.json';pin=json.loads(pinpath.read_text());pin['source_file_sha256']=schema.sha(p.read_bytes());pinpath.write_text(json.dumps(pin))
    with pytest.raises(ValueError, match='DDL identity/anchor'):
        schema.prepare(source, root=root)


@pytest.mark.parametrize('mutation', ['nullable','type','collation','order','key','engine'])
def test_expected_signature_cannot_drift_from_ddl(inputs, mutation):
    source, root=inputs
    path=root/'guest/routine_schema.json';pin=json.loads(path.read_text())
    if mutation=='nullable': pin['columns'][15][3]='YES'
    if mutation=='type': pin['columns'][0][1]='char(63)'
    if mutation=='collation': pin['columns'][0][2]='utf8mb4_bin'
    if mutation=='order': pin['columns'][0],pin['columns'][1]=pin['columns'][1],pin['columns'][0]
    if mutation=='key': pin['primary_key']=['name','db','type']
    if mutation=='engine': pin['engine']='InnoDB'
    path.write_text(json.dumps(pin))
    with pytest.raises(ValueError, match='reviewed native metadata'):
        schema.prepare(source, root=root)


def test_table_version_is_actual_source_version(inputs):
    source, root=inputs
    (source/'VERSION').write_text('MYSQL_VERSION_MAJOR=12\nMYSQL_VERSION_MINOR=3\nMYSQL_VERSION_PATCH=4\n')
    with pytest.raises(ValueError,match='source version'):
        schema.prepare(source,root=root)


def test_c_startup_helper_oracles(inputs, tmp_path):
    cc=shutil.which('cc')
    if not cc: pytest.skip('C compiler not available for isolated API shim')
    source,root=inputs;schema.prepare(source,root=root)
    binary=tmp_path/'routine-helper-test'
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror','-I',str(ROOT/'guest'),'-I',str(source/'wasm'),
                    str(ROOT/'tests/fixtures/routine_bootstrap_harness.c'),'-o',str(binary)],check=True,capture_output=True,text=True)
    run=subprocess.run([str(binary)],capture_output=True,text=True,check=True)
    assert 'PASS: fresh/restore, mode, metadata, SQL failures and context' in run.stdout


def test_driver_adapter_keeps_boot_mode_with_timing():
    spec=importlib.util.spec_from_file_location('generate_runtime',ROOT/'scripts/generate_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Actual preimage fixture supplied to the deterministic driver owner.
    text=(ROOT/'benchmarks/spikes/generated-go-integration/io-driver.go.txt').read_text()
    # This source has the pre-adapter verify helper supplied by setup_candidate.
    text+='\nfunc verifyCompiledGuest(name string) { }\n'
    out=module.adapt_driver(text)
    assert 'w.SetEnv(guestEnvironment(restore != "", diagnostic))' in out
    assert 'w.SetEnv(nil)' not in out
    with pytest.raises(ValueError,match='pinned export driver fragment'):
        module.adapt_driver(text.replace('MARIAMEM_GUEST_TIMING=1','changed'))
