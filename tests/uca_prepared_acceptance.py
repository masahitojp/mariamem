#!/usr/bin/env python3
"""Finite native differential and two-child acceptance for prepared UCA tables.

This is correctness acceptance, not a benchmark or release Qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import pymysql


def query(c, sql):
    with c.cursor() as q:
        q.execute(sql)
        return q.fetchall()


VALUES=['',' ','a','A','a ','a  ','á','a\u0301','ä','Ä','ß','ss','æ','ae','ch','cH','café','cafe','🙂','🍣','東京','大阪','ქართული','ไทย','İ','i','ı','I','K','K','x\x00y','x','é','e\u0301']
def contractions(c):
 pairs=[('h','ch'),('ch','i'),('ch','cH'),('a','a '),('á','a'),('é','e\u0301'),('เก','กเ'),('แก','เก')]
 out={}
 for coll in ['utf8mb4_uca1400_ai_ci','utf8mb4_uca1400_czech_ai_ci']:
  values=[]
  with c.cursor() as q:
   for a,b in pairs:
    q.execute(f'SELECT STRCMP(_utf8mb4%s COLLATE {coll},_utf8mb4%s COLLATE {coll})',(a,b));values.append(q.fetchone()[0])
  out[coll]=values
 return out
def semantic(c):
 out={}
 for encoding in ['utf8mb4','utf8mb3']:
  vals=[v for v in VALUES if encoding=='utf8mb4' or all(ord(x)<=65535 for x in v)]+[None]
  query(c,f'CREATE TABLE sem_{encoding}(id INT PRIMARY KEY,v VARCHAR(100) CHARACTER SET {encoding} COLLATE {encoding}_uca1400_ai_ci) ENGINE=InnoDB')
  with c.cursor() as q:q.executemany(f'INSERT INTO sem_{encoding} VALUES(%s,%s)',list(enumerate(vals)))
  table='sem_'+encoding
  out[encoding]={'ordered':query(c,f'SELECT id,HEX(v) FROM {table} ORDER BY v,id'),'groups':query(c,f'SELECT MIN(id),COUNT(*) FROM {table} GROUP BY v ORDER BY MIN(id)'),'pairs':query(c,f'SELECT a.id,b.id,STRCMP(a.v,b.v),(a.v=b.v),(a.v<b.v) FROM {table} a CROSS JOIN {table} b ORDER BY a.id,b.id'),'weights':query(c,f'SELECT id,HEX(WEIGHT_STRING(v)) FROM {table} ORDER BY id')}
  query(c,f'CREATE TABLE uniq_{encoding}(v VARCHAR(100) CHARACTER SET {encoding} COLLATE {encoding}_uca1400_ai_ci UNIQUE) ENGINE=InnoDB')
  codes=[]
  for v in vals:
   try:
    with c.cursor() as q:q.execute(f'INSERT INTO uniq_{encoding} VALUES(%s)',(v,))
    codes.append(0)
   except pymysql.err.IntegrityError as exc:
    assert exc.args[0]==1062;codes.append(1062)
  out[encoding]['unique_insert_errno']=codes
 out['contractions']=contractions(c)
 return out


def observations(c):
    out = {}
    for encoding in ['utf8mb3', 'utf8mb4']:
        table = 'sem_' + encoding
        out[encoding] = {
            'ordered': query(c, f'SELECT id,HEX(v) FROM {table} ORDER BY v,id'),
            'groups': query(c, f'SELECT MIN(id),COUNT(*) FROM {table} GROUP BY v ORDER BY MIN(id)'),
            'pairs': query(c, f'SELECT a.id,b.id,STRCMP(a.v,b.v),(a.v=b.v),(a.v<b.v) FROM {table} a CROSS JOIN {table} b ORDER BY a.id,b.id'),
            'weights': query(c, f'SELECT id,HEX(WEIGHT_STRING(v)) FROM {table} ORDER BY id'),
        }
    out['contractions'] = contractions(c)
    return json.loads(json.dumps(out))


def run(args):
    result = {'result': 'FAIL', 'platform': platform.platform(), 'machine': platform.machine()}
    if args.native_port:
        with pymysql.connect(host='127.0.0.1',port=args.native_port,user='root',database='test',autocommit=True,charset='utf8mb4') as c:
            version = query(c,'SELECT VERSION()')[0][0]
            assert version.startswith('12.3.3-'), version
            result.update(version=version, semantic=semantic(c), observations=observations(c), result='PASS_NATIVE')
        return result
    import mariamem
    expected = json.loads(args.native.read_text())
    assert expected['result'] == 'PASS_NATIVE', 'native reference did not pass'
    result['native_sha256'] = hashlib.sha256(args.native.read_bytes()).hexdigest()
    result['host_sha256'] = hashlib.sha256(args.host.read_bytes()).hexdigest()
    result['source_commit'] = subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    db = snapshot = session = None
    children = []
    cleanup_errors = []
    try:
        db = mariamem.start(host_binary=str(args.host.resolve()))
        session = db._session
        with pymysql.connect(**db.connection_info(),autocommit=True,charset='utf8mb4') as c:
            result['semantic'] = semantic(c)
            assert json.loads(json.dumps(result['semantic'])) == expected['semantic'], 'native semantic mismatch'
            assert observations(c) == expected['observations'], 'native observation mismatch'
            query(c,'CREATE TABLE isolation_probe(id INT PRIMARY KEY) ENGINE=InnoDB')
            query(c,'INSERT INTO isolation_probe VALUES(1)')
        db.wait_disconnected()
        snapshot = db.snapshot(max_forks=2)
        assert snapshot.max_forks == 2
        for ordinal in range(2):
            child = snapshot.fork(host_binary=str(args.host.resolve()))
            children.append(child)
            with pymysql.connect(**child.connection_info(),autocommit=True,charset='utf8mb4') as c:
                assert observations(c) == expected['observations'], 'child native observation mismatch'
                assert query(c,'SELECT id FROM isolation_probe ORDER BY id') == ((1,),), 'baseline not preserved'
                query(c,f'INSERT INTO isolation_probe VALUES({ordinal+2})')
        for ordinal,child in enumerate(children):
            with pymysql.connect(**child.connection_info(),autocommit=True,charset='utf8mb4') as c:
                assert query(c,'SELECT id FROM isolation_probe ORDER BY id') == ((1,),(ordinal+2,)), 'sibling write leaked'
        result['children'] = 2
        result['result'] = 'PASS'
    finally:
        for owner in [*reversed(children), snapshot, db]:
            if owner is not None:
                try:
                    owner.close()
                except Exception as exc:
                    cleanup_errors.append(str(exc))
        if session is not None:
            result['cleanup'] = {'refs':session._refs,'process_exit':session._process.poll(),'reaped':session._reaped.is_set(),'root_exists':session.root.exists()}
        result['cleanup_errors'] = cleanup_errors
        if cleanup_errors or result.get('cleanup') != {'refs':0,'process_exit':0,'reaped':True,'root_exists':False}:
            result['result'] = 'FAIL'
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    assert result['result'] == 'PASS', result
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-port',type=int)
    p.add_argument('--native',type=Path)
    p.add_argument('--host',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    if not args.native_port and (args.host is None or args.native is None):
        p.error('guest acceptance requires --host and --native')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    result = run(args)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(result['result'])


if __name__ == '__main__':
    main()
