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
