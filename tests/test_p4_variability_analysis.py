"""P4 variability statistics remain verifiable after raw/build cleanup."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/'benchmarks/forkcompare/p4_analyze.py'
DATA=ROOT/'benchmarks/forkcompare/p4-results'


def invoke(root):
    return subprocess.run([sys.executable,str(TOOL),'--evidence-dir',str(root),'--check'],
                          capture_output=True,text=True,timeout=10)


def snapshot(root):
    return {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in root.iterdir() if p.is_file()}


def reseal(root,name):
    p=root/'SHA256SUMS.json';d=json.loads(p.read_text())
    d[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    p.write_text(json.dumps(d,indent=2)+'\n')


def test_p4_check_without_temp_or_raw_is_read_only(tmp_path):
    root=tmp_path/'results';shutil.copytree(DATA,root)
    before=snapshot(root);r=invoke(root)
    assert r.returncode==0,r.stderr
    assert snapshot(root)==before


@pytest.mark.parametrize('field',['cv_percent','values_ms'])
def test_resealed_wrong_cv_or_hidden_slow_observation_is_rejected(tmp_path,field):
    root=tmp_path/'results';shutil.copytree(DATA,root);p=root/'summary.json'
    d=json.loads(p.read_text())
    if field=='cv_percent':d['rows'][0]['wall'][field]=0
    else:d['rows'][0]['wall'][field][-1]=d['rows'][0]['wall'][field][0]
    p.write_text(json.dumps(d,indent=2)+'\n');reseal(root,'summary.json')
    before=snapshot(root);r=invoke(root)
    assert r.returncode!=0 and 'recomputed summary.json differs' in r.stderr
    assert snapshot(root)==before


def test_missing_repeat_cannot_shrink_the_accepted_campaign(tmp_path):
    root=tmp_path/'results';shutil.copytree(DATA,root);p=root/'observations.json'
    d=json.loads(p.read_text());d.pop();p.write_text(json.dumps(d)+'\n');reseal(root,'observations.json')
    before=snapshot(root);r=invoke(root)
    assert r.returncode!=0 and 'expected66' in r.stderr
    assert snapshot(root)==before


def test_changed_input_identity_is_rejected(tmp_path):
    root=tmp_path/'results';shutil.copytree(DATA,root);p=root/'inputs.json'
    p.write_text(p.read_text()+' ');before=snapshot(root);r=invoke(root)
    assert r.returncode!=0 and 'checksum mismatch: inputs.json' in r.stderr
    assert snapshot(root)==before
