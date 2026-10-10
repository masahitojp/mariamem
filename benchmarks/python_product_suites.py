#!/usr/bin/env python3
"""Bounded Python adapter for the existing prepared-state suite workload.

Run one cell per process under experiment_disk.py. Native MariaDB and embedded
MariaDB versions/settings differ: these are lifecycle costs, not a speed ranking.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import resource
import subprocess
import threading
import time

import mariamem
import pymysql
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy


def connection(info):
    return pymysql.connect(**info, charset='utf8mb4', autocommit=True)


def prepare(info, rows, tables):
    with connection(info) as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE characterization(id INT PRIMARY KEY,payload VARBINARY(1024)) ENGINE=InnoDB')
            for first in range(0, rows, 128):
                batch = [(i, b'0123456789abcdef'*64) for i in range(first,min(rows,first+128))]
                cur.executemany('INSERT INTO characterization VALUES(%s,%s)', batch)
            for i in range(1,tables):
                cur.execute(f'CREATE TABLE additional_{i:03}(id INT PRIMARY KEY,value INT) ENGINE=InnoDB')


def use(info, rows):
    with connection(info) as observer, connection(info) as application:
        with observer.cursor() as a, application.cursor() as b:
            a.execute('SELECT COUNT(*) FROM characterization')
            assert a.fetchone() == (rows,)
            a.execute('SELECT OCTET_LENGTH(payload) FROM characterization WHERE id=0')
            assert a.fetchone() == (1024,)
            a.execute('SELECT CONNECTION_ID()'); one=a.fetchone()
            b.execute('SELECT CONNECTION_ID()'); assert one != b.fetchone()
            application.begin()
            b.execute('INSERT INTO characterization VALUES(%s,%s)',(rows,b'child'))
            application.commit()
            a.execute('SELECT COUNT(*) FROM characterization'); assert a.fetchone()==(rows+1,)
            application.begin()
            b.execute('DELETE FROM characterization WHERE id=0')
            application.rollback()
            a.execute('SELECT COUNT(*) FROM characterization'); assert a.fetchone()==(rows+1,)
            # Committed writes are deliberately real. Disposal/reset removes them.


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('fresh','fork','testcontainers','shared-reset'),required=True)
    parser.add_argument('--host',required=True)
    parser.add_argument('--image',required=True)
    parser.add_argument('--count',type=int,default=4)
    parser.add_argument('--workers',type=int,default=1)
    parser.add_argument('--payload-mib',type=int,default=0)
    parser.add_argument('--tables',type=int,default=1)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if min(args.count,args.workers,args.tables)<1 or args.payload_mib<0 or '@sha256:' not in args.image:
        parser.error('positive bounded counts and digest-pinned image required')
    rows=max(1,args.payload_mib*1024)
    report=dict(mode=args.mode,rows=rows,tables=args.tables,workers=args.workers,
                count=args.count,image=args.image,samples=[],completed=False)
    lock=threading.Lock()
    start=time.perf_counter()
    def cpu():
        return sum(x.ru_utime+x.ru_stime for x in (resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)))
    before=cpu()
    baseline=None;shared=None
    def native():
        container=DockerContainer(args.image).with_env('MARIADB_ROOT_PASSWORD','probe-only').with_env('MARIADB_DATABASE','test').with_exposed_ports(3306).with_kwargs(mem_limit='768m',nano_cpus=2_000_000_000)
        container.waiting_for(LogMessageWaitStrategy('port: 3306').with_startup_timeout(60))
        try:
            container.start()
            info=dict(host=container.get_container_host_ip(),port=int(container.get_exposed_port(3306)),user='root',password='probe-only',database='test')
            with connection(info) as conn:
                conn.ping()
            return container,info
        except BaseException:
            container.stop();raise
    try:
        if args.mode=='fork':
            t=time.perf_counter()
            with mariamem.start(host_binary=args.host) as db:
                prepare(db.connection_info(),rows,args.tables)
                db.wait_disconnected()
                baseline=db.snapshot()
            report['prepare_snapshot_seconds']=time.perf_counter()-t
        elif args.mode=='shared-reset':
            t=time.perf_counter();shared,shared_info=native()
            report['shared_start_seconds']=time.perf_counter()-t
        def work(index):
            row=dict(index=index);db=None;container=None;info=None;schema=None
            total=time.perf_counter()
            try:
                t=time.perf_counter()
                if args.mode in ('fresh','fork'):
                    db=baseline.fork() if baseline else mariamem.start(host_binary=args.host)
                    info=db.connection_info()
                elif args.mode=='testcontainers':container,info=native()
                else:
                    info=dict(shared_info);schema=f'product_{index}'
                    with connection(shared_info) as conn:
                        with conn.cursor() as cur:cur.execute(f'CREATE DATABASE {schema}')
                    info['database']=schema
                with connection(info) as conn:
                    with conn.cursor() as cur:
                        cur.execute('SELECT 1,VERSION()');_,version=cur.fetchone()
                row['ready_seconds']=time.perf_counter()-t;row['server_version']=version
                t=time.perf_counter()
                if args.mode!='fork':prepare(info,rows,args.tables)
                row['prepare_seconds']=time.perf_counter()-t
                t=time.perf_counter();use(info,rows);row['sql_seconds']=time.perf_counter()-t
            finally:
                t=time.perf_counter()
                if db:db.close()
                if container:container.stop()
                if schema:
                    with connection(shared_info) as conn:
                        with conn.cursor() as cur:cur.execute(f'DROP DATABASE {schema}')
                row['cleanup_seconds']=time.perf_counter()-t
            row['test_seconds']=time.perf_counter()-total
            with lock:report['samples'].append(row)
        if args.workers==1:
            for i in range(args.count):work(i)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:list(pool.map(work,range(args.count)))
        report['completed']=True
    finally:
        if baseline:baseline.close()
        if shared:shared.stop()
        report['suite_wall_seconds']=time.perf_counter()-start
        report['runner_and_reaped_host_cpu_seconds']=cpu()-before
        report['cpu_scope']='Python runner + reaped host/helper children; excludes Docker daemon/VM/container CPU'
        report['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        report['samples'].sort(key=lambda r:r['index'])
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
