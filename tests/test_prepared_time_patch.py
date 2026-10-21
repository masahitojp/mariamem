"""Experimental source patch pre/postimage and failure checks; no guest build."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('time_patch', ROOT/'scripts/prepared_time_patch.py')
patch=importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def tree(tmp_path):
    root,source=tmp_path/'root',tmp_path/'source'
    (root/'guest').mkdir(parents=True)
    (source/'sql').mkdir(parents=True)
    # Small synthetic source for failure injection. Actual complete pinned
    # upstream source is separately applied and hash-verified in the receipt.
    before=b'old\n'
    delta=b'--- a/sql/sql_prepare.cc\n+++ b/sql/sql_prepare.cc\n@@ -1 +1 @@\n-old\n+new\n'
    (source/'sql/sql_prepare.cc').write_bytes(before)
    pin={'source_commit':'fixed','file':'sql/sql_prepare.cc','before_sha256':sha(before),
         'after_sha256':sha(b'new\n'),'patch_sha256':sha(delta)}
    (root/'guest/input.json').write_text(json.dumps({'source_commit':'fixed'}))
    (root/'guest/experimental.patch').write_bytes(delta)
    (root/'guest/prepared_time_patch.json').write_text(json.dumps(pin))
    return root,source


def test_exact_apply_and_double_application(tree):
    root,source=tree
    patch.apply(source,root)
    assert (source/'sql/sql_prepare.cc').read_bytes()==b'new\n'
    with pytest.raises(ValueError,match='preimage'):
        patch.apply(source,root)


@pytest.mark.parametrize('field,value', [('source_commit','other'),('file','other.cc'),
    ('patch_sha256','0'*64),('before_sha256','0'*64),('after_sha256','0'*64)])
def test_pin_mutations_rejected(tree,field,value):
    root,source=tree
    p=root/'guest/prepared_time_patch.json'
    pin=json.loads(p.read_text());pin[field]=value;p.write_text(json.dumps(pin))
    with pytest.raises(ValueError):
        patch.apply(source,root)


def test_changed_complete_source_rejected_before_mutation(tree):
    root,source=tree
    p=source/'sql/sql_prepare.cc';p.write_bytes(b'unrelated addition\nold\n')
    with pytest.raises(ValueError,match='preimage'):
        patch.apply(source,root)
    assert p.read_bytes()==b'unrelated addition\nold\n'


def test_checked_command_failure_is_not_hidden(tree,monkeypatch):
    root,source=tree
    def fail(command,**kwargs):
        assert '--batch' in command and '--forward' in command and '--fuzz=0' in command
        assert kwargs['check'] is True
        raise subprocess.CalledProcessError(1,command)
    monkeypatch.setattr(patch.subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError):
        patch.apply(source,root)


def test_repository_patch_input_binding():
    assert patch.inputs(ROOT)['before_sha256']=='2e6d7bebe2d332b3b95690d61c903ecd749b94a04a04820ebd9bc5d8a4957ed3'
