"""Runtime-independent module/platform acceptance still fails closed."""
import copy
import os
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from consumer_acceptance import MODULE, verify_resolved_commit, bind_remote_origin, isolated_env

SHA = "a" * 40
TAG = "v0.4.2"

def record():
    return {"Path":MODULE,"Version":TAG,"Sum":"h1:fixture","Origin":{"Hash":SHA}}

def test_exact_source_tag_and_remote_origin():
    remote = record()
    resolved = {k:v for k,v in remote.items() if k != "Origin"}
    assert bind_remote_origin(resolved,remote,SHA,TAG) == remote
    verify_resolved_commit(remote,SHA,TAG)

@pytest.mark.parametrize("change", ["sha","module","tag","sum","origin"])
def test_incomplete_or_mismatched_module_rejected(change):
    value = record()
    if change == "sha": value["Origin"]["Hash"] = "b"*40
    if change == "module": value["Path"] = "example.com/other"
    if change == "tag": value["Version"] = "v0.4.1"
    if change == "sum": value["Sum"] = ""
    if change == "origin": value.pop("Origin")
    with pytest.raises(ValueError): verify_resolved_commit(value,SHA,TAG)

@pytest.mark.parametrize("key", ["Path","Version"])
def test_remote_binding_rejects_another_module_identity(key):
    remote=record();remote[key]="wrong"
    with pytest.raises(ValueError): bind_remote_origin(record(),remote,SHA,TAG)

def test_isolation_removes_tokens_and_runtime_overrides(tmp_path,monkeypatch):
    for key in ["GH_TOKEN","GITHUB_TOKEN","MARIAMEM_NATIVE_DIR","WASMER_DIR","GOFLAGS","DYLD_LIBRARY_PATH"]:
        monkeypatch.setenv(key,"fixture-secret")
    env=isolated_env(tmp_path)
    for key in ["GH_TOKEN","GITHUB_TOKEN","MARIAMEM_NATIVE_DIR","WASMER_DIR","DYLD_LIBRARY_PATH"]:
        assert key not in env
    assert env["GOTOOLCHAIN"] == "local"
    assert env["GOFLAGS"] == "-modcacherw"
    assert Path(env["TMPDIR"]).is_dir()


def test_public_module_origin_alone_cannot_hide_changed_bytes(tmp_path):
    from consumer_acceptance import verify_module_files
    root=tmp_path/'accepted'; root.mkdir()
    (root/'internal').mkdir(); (root/'release').mkdir()
    for name in ('go.mod','go.sum','LICENSE','release/inputs.lock.json','mariamem.go','internal/host.go'):
        (root/name).write_text('accepted source')
    import shutil
    downloaded=tmp_path/'downloaded'; shutil.copytree(root,downloaded)
    resolved={**record(), 'Dir':str(downloaded)}
    assert verify_module_files(resolved,root)
    (downloaded/'internal/host.go').write_text('changed runtime')
    with pytest.raises(ValueError,match='library files differ'): verify_module_files(resolved,root)
    (downloaded/'internal/host.go').write_text('accepted source')
    (downloaded/'internal/injected.go').write_text('injected runtime')
    with pytest.raises(ValueError,match='library files differ'): verify_module_files(resolved,root)


@pytest.mark.parametrize('prefix', ['mariamem/', 'mariamem.data/purelib/mariamem/'])
def test_installed_package_is_bound_to_actual_wheel_inventory(tmp_path,prefix):
    from consumer_acceptance import verify_installed_files
    import zipfile
    wheel=tmp_path/'package.whl'; package=tmp_path/'installed'; package.mkdir()
    files={'__init__.py':b'package', '_native/mariamem-host':b'host'}
    with zipfile.ZipFile(wheel,'w') as archive:
        for name,data in files.items(): archive.writestr(prefix+name,data)
    for name,data in files.items():
        path=package/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    assert verify_installed_files(wheel,package)==sorted(files)
    (package/'_native/mariamem-host').write_bytes(b'changed host')
    with pytest.raises(ValueError,match='mismatch'): verify_installed_files(wheel,package)
    (package/'_native/mariamem-host').write_bytes(b'host')
    (package/'extra.py').write_text('extra')
    with pytest.raises(ValueError,match='inventory differs'): verify_installed_files(wheel,package)


@pytest.mark.parametrize('invalid', [False,True])
def test_shared_orm_oracles_reject_incomplete_or_skipped_cases(tmp_path,invalid):
    from consumer_acceptance import ORM_MODES, verify_gorm_cases, verify_sqlalchemy_cases
    import json
    assert ORM_MODES==('start','fork','fork','start')
    gorm=tmp_path/'gorm.json'; gorm.write_text(json.dumps({'passed':True,'cases':list(range(7 if invalid else 8))}))
    sqlalchemy=tmp_path/'sa.xml'
    sqlalchemy.write_text('<testsuites><testsuite tests="11" failures="0" errors="0" skipped="'+str(int(invalid))+'"/></testsuites>')
    if invalid:
        with pytest.raises(ValueError): verify_gorm_cases(gorm)
        with pytest.raises(ValueError): verify_sqlalchemy_cases(sqlalchemy)
    else:
        assert verify_gorm_cases(gorm)==8 and verify_sqlalchemy_cases(sqlalchemy)==11
