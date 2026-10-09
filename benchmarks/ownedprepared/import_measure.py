"""Exact-SDK import and child-suite measurement; no public backing metadata."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import errno
import json
import os
from pathlib import Path
import resource
import subprocess
import threading
import time

import mariamem
import pymysql


def fd_count():
    if Path('/proc/self/fd').is_dir():
        return len(os.listdir('/proc/self/fd'))
    import fcntl
    count = 0
    for fd in range(resource.getrlimit(resource.RLIMIT_NOFILE)[0]):
        try:
            fcntl.fcntl(fd, fcntl.F_GETFD)
            count += 1
        except OSError as error:
            if error.errno != errno.EBADF:
                raise
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--label', choices=('baseline', 'candidate'), required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--forks', type=int, default=16)
    parser.add_argument('--tables',type=int,default=1)
    parser.add_argument('--capture',action='store_true')
    parser.add_argument('--capture-destination')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--workload', choices=('read', 'crud', 'app-connections'), default='read')
    parser.add_argument('--fd-snapshots', type=int, default=0)
    parser.add_argument('--helper', required=True)
    args = parser.parse_args()
    if args.capture and not args.capture_destination:
        parser.error('capture requires a disposable destination')
    if args.forks < 1 or args.workers < 1 or args.fd_snapshots < 0:
        parser.error('positive forks/workers and nonnegative fd-snapshots required')
    operations, resources = [], {}
    lock = threading.Lock()

    def cpu():
        own = resource.getrusage(resource.RUSAGE_SELF)
        child = resource.getrusage(resource.RUSAGE_CHILDREN)
        return own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime

    def measure(name, fn):
        start = time.perf_counter()
        result = fn()
        # Child CPU appears on reap, so do not ascribe it to individual phases.
        with lock:
            operations.append(dict(name=name, seconds=time.perf_counter()-start))
        return result

    def probe(name, *pids):
        resources[name] = json.loads(subprocess.check_output([args.helper, *map(str, pids)]))

    def acquire():
        if args.label == 'candidate':
            return mariamem.load_snapshot(args.artifact, host_binary=args.host)
        return mariamem.Snapshot.open(args.artifact)

    manifest = json.loads((Path(args.artifact)/'manifest.json').read_text())
    files = [entry for entry in manifest['entries'].values() if entry['kind']=='file']
    result = dict(label=args.label, forks=args.forks, workers=args.workers, tables=args.tables,
                  workload=args.workload, prepared_files=len(files),
                  prepared_bytes=sum(entry['bytes'] for entry in files),
                  operations=operations, resources=resources, fds_before=fd_count())
    probe('before', os.getpid())
    begun, start_cpu = time.perf_counter(), cpu()
    saved = measure('import', acquire)
    result['fds_snapshot'] = fd_count()
    probe('imported', os.getpid())
    try:
        if args.capture:
            child=measure('source_ready',lambda:saved.fork(host_binary=args.host))
            try:
                fixed=measure('snapshot',child.snapshot)
                measure('created_snapshot_close',fixed.close)
            finally:
                child.close()
            child=measure('persist_source_ready',lambda:saved.fork(host_binary=args.host))
            try:
                def persist():
                    if args.label=='candidate':
                        return child.snapshot_to(args.capture_destination)
                    return child.snapshot(args.capture_destination)
                fixed=measure('snapshot_persisted',persist)
                measure('persisted_snapshot_close',fixed.close)
            finally:
                child.close()
        elif args.fd_snapshots:
            others = []
            try:
                for index in range(1, args.fd_snapshots):
                    try:
                        others.append(acquire())
                    except OSError as error:
                        if error.errno not in (errno.EMFILE,errno.ENFILE):
                            raise
                        result['fd_limit_error']=str(error)
                        break
                    if index+1 in (4,16):
                        resources[f'fds_{index+1}_snapshots'] = fd_count()
                result.update(fd_snapshots_requested=args.fd_snapshots,fd_snapshots=1+len(others), fds_all_snapshots=fd_count(),
                              fd_soft_limit=resource.getrlimit(resource.RLIMIT_NOFILE)[0],
                              fd_hard_limit=resource.getrlimit(resource.RLIMIT_NOFILE)[1])
                probe('all_snapshots', os.getpid())
            finally:
                for item in reversed(others):
                    item.close()
        else:
            def work(index):
                child = measure(f'fork_ready_{index:02}', lambda:saved.fork(host_binary=args.host))
                try:
                    if index==0 and args.workers==1:
                        probe('first_ready', os.getpid(), child.diagnostics['host_pid'])
                    def use():
                        with pymysql.connect(**child.connection_info(), autocommit=True) as observer:
                            with observer.cursor() as cursor:
                                cursor.execute('SELECT payload FROM characterization WHERE id=0')
                                assert len(cursor.fetchone()[0])==1024
                                cursor.execute('SELECT COUNT(*) FROM characterization')
                                rows = cursor.fetchone()[0]
                                assert rows > 0
                            if args.workload != 'read':
                                with pymysql.connect(**child.connection_info()) as application:
                                    with application.cursor() as cursor:
                                        cursor.execute('INSERT INTO characterization VALUES(%s,%s)',(rows,b'c'*1024))
                                        cursor.execute('UPDATE characterization SET payload=%s WHERE id=0',(b'u'*1024,))
                                        application.commit()
                                    with observer.cursor() as cursor:
                                        cursor.execute('SELECT COUNT(*) FROM characterization')
                                        assert cursor.fetchone()[0]==rows+1
                                    with application.cursor() as cursor:
                                        cursor.execute('DELETE FROM characterization WHERE id=%s',(rows,))
                                        application.commit()
                                        cursor.execute('DELETE FROM characterization WHERE id=0')
                                        application.rollback()
                                    with observer.cursor() as cursor:
                                        cursor.execute('SELECT COUNT(*) FROM characterization')
                                        assert cursor.fetchone()[0]==rows
                        child.wait_disconnected()
                    measure(f'point_count_{args.workload}_{index:02}',use)
                finally:
                    measure(f'child_close_{index:02}',child.close)
            loop_begun=time.perf_counter()
            if args.workers==1:
                for index in range(args.forks):
                    work(index)
            else:
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    list(pool.map(work,range(args.forks)))
            result['fork_suite_wall_seconds']=time.perf_counter()-loop_begun
            probe('children_closed',os.getpid())
    finally:
        measure('snapshot_close',saved.close)
    result['suite_wall_seconds'] = time.perf_counter()-begun
    result['suite_cpu_seconds'] = cpu()-start_cpu
    result['suite_cpu_scope']='RUSAGE_SELF + reaped RUSAGE_CHILDREN; includes DB hosts and counter-helper CPU; diagnostic-inclusive'
    result['parallel_resource_sampling']='before/after child loop only; no simultaneous-child peak sample'
    result['suite_operation_seconds'] = sum(value['seconds'] for value in operations)
    result['sum_of_operation_seconds'] = result['suite_operation_seconds']
    product=result['suite_operation_seconds']
    if args.workers>1:
        product=result['fork_suite_wall_seconds']+sum(value['seconds'] for value in operations if value['name'] in ('import','snapshot_close'))
    result['suite_product_seconds']=product
    result['diagnostic_overhead_seconds']=result['suite_wall_seconds']-product
    result['fds_after'] = fd_count()
    probe('after',os.getpid())
    if result['fds_after'] > result['fds_before']:
        raise RuntimeError(f"FD accumulation: {result['fds_before']} -> {result['fds_after']}")
    operations.sort(key=lambda value:value['name'])
    Path(args.out).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    main()
