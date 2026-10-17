"""Real private handoff -> mapped child -> native root -> grandchild oracle."""
import json
import os
from pathlib import Path
import shutil

import mariamem
import pymysql


def query(db,sql):
    with pymysql.connect(**db.connection_info(),autocommit=True) as c:
        with c.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


def test_mapped_child_becomes_independent_root(tmp_path,monkeypatch):
    evidence=Path(os.environ['OWNED_ROOT_EVIDENCE']);evidence.mkdir(exist_ok=True)
    trace=evidence/'traces';trace.mkdir(exist_ok=True)
    monkeypatch.setenv('MARIAMEM_TIMING_DIR',str(trace))
    original=Path(os.environ['MARIAMEM_TEST_HOST'])
    alternate=tmp_path/'alternate-host';shutil.copy2(original,alternate);alternate.chmod(0o755)
    with mariamem.start(host_binary=original) as source:
        query(source,'CREATE TABLE mapped_lineage(id INT PRIMARY KEY,value INT) ENGINE=InnoDB')
        query(source,'INSERT INTO mapped_lineage VALUES (1,10)')
        source.wait_disconnected()
        with source.snapshot() as baseline:
            with baseline.fork(host_binary=alternate) as mapped:
                query(mapped,'UPDATE mapped_lineage SET value=20 WHERE id=1')
                mapped.wait_disconnected()
                with mapped.snapshot() as derived:
                    with derived.fork() as child:
                        assert query(child,'SELECT value FROM mapped_lineage WHERE id=1')==((20,),)
                        query(child,'UPDATE mapped_lineage SET value=30 WHERE id=1')
                    with derived.fork() as sibling:
                        assert query(sibling,'SELECT value FROM mapped_lineage WHERE id=1')==((20,),)
            with baseline.fork() as untouched:
                assert query(untouched,'SELECT value FROM mapped_lineage WHERE id=1')==((10,),)
            assert not list(baseline._session.root.glob('handoff-*'))
    captures=[json.loads(p.read_text()) for p in trace.glob('*-snapshot_capture-*.json')]
    assert len(captures)==2
    totals={}
    for capture in captures:
        for event in capture['events']:
            name=event['name']
            if name.startswith('root/mapped-'):
                totals[name]=totals.get(name,0)+event.get('bytes_read',0)
    assert totals['root/mapped-source/hash/hash']>0
    assert totals['root/mapped-source/hash/hash']==totals['root/mapped-target/hash/hash']
    assert totals['root/mapped-copy/mapped/copy']>0
    (evidence/'result.json').write_text(json.dumps({'result':'PASS','capture_count':2,'mapped_work':totals,'observed':['handoff strict receiver','mapped resnapshot materialization','grandchild data','sibling isolation','original baseline unchanged','handoff cleanup']},indent=2)+'\n')
