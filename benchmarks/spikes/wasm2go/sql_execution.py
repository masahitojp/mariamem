#!/usr/bin/env python3
"""Exercise the unchanged mariamem guest framing and SQL expectations."""
import argparse
import json
from pathlib import Path
import select
import struct
import subprocess
import time


class Guest:
    def __init__(self, command, log, env=None):
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=log, bufsize=0, env=env)
        self.request = 0

    def read(self, n, timeout=30):
        out = b''
        limit = time.monotonic() + timeout
        while len(out) < n:
            if not select.select([self.proc.stdout], [], [], max(0,limit-time.monotonic()))[0]:
                raise TimeoutError('guest response timeout')
            chunk = self.proc.stdout.read(n-len(out))
            if not chunk:
                raise EOFError('guest exited before response')
            out += chunk
        return out

    def frame(self):
        n = struct.unpack('<I',self.read(4))[0]
        if n > 16*1024*1024:
            raise ValueError('unexpected response length')
        return json.loads(self.read(n))

    def call(self, op, text='', slot=0):
        self.request += 1
        payload = struct.pack('<BII',op,self.request,slot) + text.encode()
        self.proc.stdin.write(struct.pack('<I',len(payload))+payload)
        self.proc.stdin.flush()
        row = self.frame()
        assert row['request_id'] == self.request and row['connection_id'] == slot
        return row['result']

    def stop(self):
        self.proc.stdin.write(b'\0'*4)
        self.proc.stdin.flush()
        return self.proc.wait(timeout=30)


def workload(g, records):
    ready = g.frame()['result']
    assert ready == {'ready':True,'api_version':2,'max_sessions':16,'snapshot_version':1}
    records.append(dict(sql='READY',result=ready))
    opened = g.call(1)
    assert opened['ok']
    records.append(dict(sql='OPEN',result=opened))
    cases = [
        ('SELECT 1', [['1']]),
        ('CREATE TABLE spike(id INT PRIMARY KEY, v INT NOT NULL) ENGINE=InnoDB', None),
        ('INSERT INTO spike VALUES (1,10),(2,20)', None),
        ('SELECT id,v FROM spike ORDER BY id', [['1','10'],['2','20']]),
        ('UPDATE spike SET v=11 WHERE id=1', None),
        ('DELETE FROM spike WHERE id=2', None),
        ('START TRANSACTION', None),
        ('INSERT INTO spike VALUES (3,30)', None),
        ('COMMIT', None),
        ('START TRANSACTION', None),
        ('UPDATE spike SET v=99 WHERE id=1', None),
        ('INSERT INTO spike VALUES (4,40)', None),
        ('ROLLBACK', None),
        ('SELECT id,v FROM spike ORDER BY id', [['1','11'],['3','30']]),
    ]
    for sql, expected in cases:
        r = g.call(2,sql)
        records.append(dict(sql=sql,result=r))
        assert r['ok'], (sql,r)
        if expected is not None:
            decoded = [[bytes.fromhex(c['$h']).decode() if c is not None else None for c in row] for row in r['rows']]
            assert decoded == expected, (sql,decoded)
    for sql, errno in [('INSERT INTO spike VALUES (1,88)',1062),
                       ('INSERT INTO spike VALUES (5,NULL)',1048),
                       ('SELECT * FROM missing_spike_table',1146),
                       ('SELECT FROM',1064)]:
        r = g.call(2,sql)
        records.append(dict(sql=sql,result=r))
        assert not r['ok'] and r['errno'] == errno, (sql,r)
    # A second ordinary session proves guest TLS and transaction isolation together.
    assert g.call(1,slot=1)['ok']
    assert g.call(2,'START TRANSACTION')['ok']
    assert g.call(2,'INSERT INTO spike VALUES (6,60)')['ok']
    r = g.call(2,'SELECT COUNT(*) FROM spike',slot=1)
    records.append(dict(sql='second session sees committed rows only',result=r))
    assert r['rows'][0][0]['$h'] == '32'
    assert g.call(2,'ROLLBACK')['ok']
    assert g.call(3,slot=1)['closed']
    assert g.call(3)['closed']
    assert g.stop() == 0
    records.append(dict(sql='SHUTDOWN',exit_code=0))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--module',type=Path,help='production Wasmer control: supply AOT module')
    p.add_argument('--wasmer-home',type=Path)
    a = p.parse_args()
    command = [str(a.binary.resolve())]
    if a.module:
        if not a.wasmer_home: p.error('--wasmer-home required for production control')
        command += ['run',str(a.module.resolve()),'--no-tty']
    import os
    if a.wasmer_home: os.environ['WASMER_DIR'] = str(a.wasmer_home.resolve())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    rows=[]; result={'completed':False,'records':rows}
    with a.output.with_suffix('.log').open('wb') as log:
        g = Guest(command,log)
        try:
            workload(g,rows)
            result['completed']=True
        except Exception as err:
            result['failure']=repr(err)
        finally:
            if g.proc.poll() is None:
                g.proc.kill(); g.proc.wait()
            result['exit_code']=g.proc.returncode
            a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['completed']: raise SystemExit(1)


if __name__ == '__main__': main()
