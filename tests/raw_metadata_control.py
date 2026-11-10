"""Paired C-extension outcome plus an independent raw-wire metadata oracle."""
import argparse
import json
from pathlib import Path
import struct
import sys
import mysql.connector
import pymysql
from v06_prepared_p1_probe import prepare, close_ping
from v06_prepared_call_probe import result_chain


def observe(info, *, with_cext=True):
    outcome = None
    if with_cext:
        with mysql.connector.connect(use_pure=False, **info) as c:
            with c.cursor() as q:
                q.execute('DROP TABLE IF EXISTS raw_meta_cext')
                q.execute('CREATE TABLE raw_meta_cext(id INT PRIMARY KEY) ENGINE=InnoDB')
                q.execute('INSERT INTO raw_meta_cext VALUES(1)')
                c.commit()
                q.execute('SELECT VERSION()')
                version = q.fetchone()[0]
            q = c.cursor(prepared=True)
            sql = 'SELECT * FROM raw_meta_cext ORDER BY id'
            q.execute(sql)
            assert q.fetchall() == [(1,)]
            with c.cursor() as ddl:
                ddl.execute('ALTER TABLE raw_meta_cext ADD COLUMN extra INT DEFAULT 9')
            try:
                q.execute(sql)
            except mysql.connector.Error as error:
                outcome = {'errno':error.errno}
            else:
                outcome = {'errno':0, 'rows':q.fetchall()}
    with pymysql.connect(**info, autocommit=True) as c:
        with c.cursor() as q:
            q.execute('SELECT VERSION()')
            version = q.fetchone()[0]
            q.execute('DROP TABLE IF EXISTS raw_meta_wire')
            q.execute('CREATE TABLE raw_meta_wire(id INT PRIMARY KEY) ENGINE=InnoDB')
            q.execute('INSERT INTO raw_meta_wire VALUES(1),(2)')
        sid, _ = prepare(c, 'SELECT * FROM raw_meta_wire ORDER BY id')
        payload = struct.pack('<IBI', sid, 0, 1)
        before = result_chain(c, payload)
        with c.cursor() as q:
            q.execute('ALTER TABLE raw_meta_wire ADD COLUMN extra INT DEFAULT 9')
        after = result_chain(c, payload)
        assert len(before) == len(after) == 1
        assert len(before[0]['columns']) == 1 and len(after[0]['columns']) == 2
        assert before[0]['rows'] == ['000001000000', '000002000000']
        assert after[0]['rows'] == ['00000100000009000000', '00000200000009000000']
        close_ping(c, sid)
    return {'version':version, 'connector':mysql.connector.__version__,
            'python':sys.version, 'cext':outcome, 'wire_before':before, 'wire_after':after}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--wire-only', action='store_true')
    a = p.parse_args()
    record = observe(dict(host='127.0.0.1', port=a.port, user='root', database='test'), with_cext=not a.wire_only)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(record, indent=2)+'\n')
    assert record['version'].startswith('12.3.3')
    if not a.wire_only:
        assert record['cext']['errno'] == 2057, record
