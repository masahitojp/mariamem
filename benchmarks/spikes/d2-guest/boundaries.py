"""Real Python API boundaries for the isolated E cold-handoff prototype."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'python'))
import mariamem
import pymysql
import d2_python
d2_python.install()

def query(c,sql):
    with c.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()

def connect(db):
    return pymysql.connect(**db.connection_info(),autocommit=False)

def create(db):
    with contextlib.closing(connect(db)) as c:
        query(c,'CREATE TABLE items (id INT PRIMARY KEY, v INT) ENGINE=InnoDB')
        query(c,'INSERT INTO items VALUES (1,10)')
        c.commit()
    db.wait_disconnected()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['e','d2'],required=True)
    p.add_argument('--host',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.host=args.host.resolve();args.output=args.output.resolve()
    args.output.mkdir(parents=True)
    os.environ['MARIAMEM_E_MODE']='handoff'
    os.environ['MARIAMEM_D']='0'
    os.environ['MARIAMEM_D2']='1' if args.mode=='d2' else '0'
    os.environ.pop('MARIAMEM_E_AUDIT',None)
    os.environ['MARIAMEM_E_OUT']=str(args.output)
    checks=[]
    failures=[]
    try:
        with mariamem.start(host_binary=str(args.host),log_path=args.output/'lifecycle.log') as db:
            create(db)
            c=connect(db)
            query(c,'UPDATE items SET v=11 WHERE id=1')
            try:
                db.snapshot()
                raise AssertionError('active transaction accepted')
            except mariamem.HostError as exc:
                assert exc.code=='transaction_active' and not exc.closed,(exc.code,exc.closed)
            assert query(c,'SELECT v FROM items WHERE id=1')==((11,),)
            c.rollback();c.close();db.wait_disconnected()
            checks.append('transaction-rejected-source-still-usable')
            with db.snapshot() as baseline:
                with baseline.fork(log_path=args.output/'first.log') as first, baseline.fork(log_path=args.output/'second.log') as second:
                    baseline.close()
                    with contextlib.closing(connect(first)) as c:
                        assert query(c,'SELECT v FROM items')==((10,),)
                        query(c,'UPDATE items SET v=20');c.commit()
                    first.wait_disconnected()
                    with contextlib.closing(connect(second)) as c:
                        assert query(c,'SELECT v FROM items')==((10,),)
                        c.commit()
                    second.wait_disconnected()
                    checks.append('two-live-children-survive-baseline-close-and-isolate')
                    # D2 shares retained blocks; E keeps its existing export path.
                    with first.snapshot() as derived:
                        with derived.fork(log_path=args.output/'derived.log') as third:
                            with contextlib.closing(connect(third)) as c:
                                assert query(c,'SELECT v FROM items')==((20,),)
                                c.commit()
                        with contextlib.closing(connect(second)) as c:
                            assert query(c,'SELECT v FROM items')==((10,),)
                            c.commit()
                    checks.append('derived-retains-changes-and-sibling-isolation')
        if args.mode=='d2':
            dest=args.output/'persisted'
            with mariamem.start(host_binary=str(args.host),log_path=args.output/'persist.log') as db:
                create(db)
                with db.snapshot_to(dest) as saved:
                    assert not isinstance(saved,d2_python.D2Snapshot)
                    with saved.fork(log_path=args.output/'persist-child.log') as child:
                        with contextlib.closing(connect(child)) as c:
                            assert query(c,'SELECT v FROM items')==((10,),)
                            c.commit()
            import shutil
            shutil.rmtree(dest)
            checks.append('snapshot-to-existing-format-import-and-fork-pass')
        for fault in ['before_move','after_move','corrupt_after_hash','publish_after_move']+(['receiver_corrupt'] if args.mode=='d2' else []):
            os.environ['MARIAMEM_E_FAULT']=fault
            dest=args.output/('failed-'+fault)
            with mariamem.start(host_binary=str(args.host),log_path=args.output/(fault+'.log')) as db:
                create(db)
                try:
                    db.snapshot() if args.mode=='d2' else db.snapshot_to(dest)
                    raise AssertionError('fault was accepted: '+fault)
                except mariamem.HostError as exc:
                    assert exc.closed,(fault,exc.code,str(exc))
                    if args.mode=='d2':
                        expected={'corrupt_after_hash':'D2 target hash mismatch','receiver_corrupt':'D2 content mismatch'}.get(fault,'injected '+fault)
                        assert expected in str(exc),(fault,str(exc))
                    failures.append({'fault':fault,'code':exc.code,'message':str(exc),'closed':exc.closed})
                    assert db._process.poll() is not None,fault
                assert not dest.exists(),fault
            checks.append(fault+'-rejected-source-closed-destination-removed')
        os.environ.pop('MARIAMEM_E_FAULT',None)
        # Receiver-side corruption oracle, using the unchanged Python adopter.
        temporary=tempfile.TemporaryDirectory(dir=args.output)
        with temporary as d:
            root=Path(d)/'snapshot'
            root.mkdir();(root/'data').mkdir()
            import hashlib
            from mariamem.snapshot import _host_identity
            _,build=_host_identity({'host_binary':str(args.host)})
            (root/'data/a').write_bytes(b'bad!')
            manifest={'format':'mariamem-cold-snapshot','version':1,'wasm_sha256':build,'source_storage':'memory',
                      'entries':{'.':{'kind':'directory'},'a':{'kind':'file','bytes':4,'sha256':hashlib.sha256(b'good').hexdigest()}}}
            (root/'manifest.json').write_text(json.dumps(manifest))
            try:
                mariamem.Snapshot._created(root,{'host_binary':str(args.host)},temporary)
                raise AssertionError('receiver accepted same-size corruption')
            except ValueError as exc:
                assert 'manifest mismatch' in str(exc),str(exc)
            checks.append('unchanged-python-acquisition-rejects-same-size-corruption')
        scratch=Path(os.environ['TMPDIR'])
        leftovers=[p.name for p in scratch.iterdir() if p.name.startswith('mariamem-')]
        assert not leftovers,leftovers
        checks.append('no-owned-runtime-temp-directories-left')
        result={'status':'PASS','checks':checks,'failures':failures}
    except BaseException as exc:
        result={'status':'FAIL','checks':checks,'error':repr(exc)}
        raise
    finally:
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
