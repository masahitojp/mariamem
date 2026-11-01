"""Saved same-host results remain independently checkable after experiment cleanup."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/'benchmarks/forkcompare/analyze.py'
DATA=ROOT/'benchmarks/forkcompare/results'


def invoke(root):
    return subprocess.run([sys.executable,str(TOOL),'--evidence-dir',str(root),'--check'],
                          capture_output=True,text=True,timeout=10)


def snapshot(root):
    return {p.relative_to(root).as_posix():(p.read_bytes(),p.stat().st_mtime_ns)
            for p in root.rglob('*') if p.is_file()}


def reseal(root,name):
    manifest=root/'SHA256SUMS.json'
    d=json.loads(manifest.read_text())
    d[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    manifest.write_text(json.dumps(d,indent=2)+'\n')


def test_check_needs_no_build_or_raw_and_preserves_all_evidence(tmp_path):
    root=tmp_path/'evidence';shutil.copytree(DATA,root)
    assert not (tmp_path/'temp').exists()
    before=snapshot(root);r=invoke(root)
    assert r.returncode==0,r.stderr
    assert snapshot(root)==before


@pytest.mark.parametrize('name',['summary.json','summary.csv'])
def test_resealed_wrong_summary_is_rejected_without_writes(tmp_path,name):
    root=tmp_path/'evidence';shutil.copytree(DATA,root);p=root/name
    if name.endswith('.json'):
        d=json.loads(p.read_text());d['rows'][0]['median_wall_ms']+=1
        p.write_text(json.dumps(d,indent=2)+'\n')
    else:
        p.write_text(p.read_text().replace('mariamem','wrong-backend',1))
    reseal(root,name);before=snapshot(root);r=invoke(root)
    assert r.returncode!=0 and 'recomputed' in r.stderr
    assert snapshot(root)==before


def test_failed_warmup_oracle_cannot_be_accepted_by_compact_check(tmp_path):
    root=tmp_path/'evidence';shutil.copytree(DATA,root);p=root/'observations.json'
    d=json.loads(p.read_text());r=next(r for r in d if r['kind']=='micro' and r['warmup'])
    r['samples'][0]['oracle']=False;p.write_text(json.dumps(d)+'\n');reseal(root,'observations.json')
    before=snapshot(root);result=invoke(root)
    assert result.returncode!=0
    assert snapshot(root)==before


def test_modified_input_identity_is_rejected(tmp_path):
    root=tmp_path/'evidence';shutil.copytree(DATA,root);p=root/'inputs.json'
    p.write_text(p.read_text()+' ');before=snapshot(root);r=invoke(root)
    assert r.returncode!=0 and 'checksum mismatch: inputs.json' in r.stderr
    assert snapshot(root)==before
