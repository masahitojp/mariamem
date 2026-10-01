#!/usr/bin/env python3
"""Observe ordinary idle and SQL quiesce; never use these samples as snapshots."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).parents[1] / 'wasm2go'))
from sql_execution import Guest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--prepared-files', type=Path, required=True)
    p.add_argument('--linear-image', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--runs', type=int, default=3)
    a = p.parse_args()
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = {'boundary': 'fresh execution over accepted clean prepared files; NOT ready-heap reentry', 'runs': []}
    for trial in range(a.runs):
        d = out / str(trial)
        d.mkdir(exist_ok=True)
        env = dict(os.environ, COW_CONTROL_DIR=str(d), COW_LINEAR_MODE='cow', COW_LINEAR_IMAGE=str(a.linear_image.resolve()),
                   PREPARED_FS_IMAGE=str(a.prepared_files.resolve()), PREPARED_FS_MODE='cow')
        row = {'trial': trial, 'stages': [], 'sql': [], 'completed': False}
        results['runs'].append(row)
        with (d / 'guest.log').open('wb') as log:
            g = Guest([str(a.binary.resolve()), 'measure'], log, env=env)
            try:
                assert g.frame()['result']['ready']
                control = json.loads((d / 'control.json').read_text())

                def sample(label):
                    with urllib.request.urlopen(f"http://127.0.0.1:{control['port']}/runtime", timeout=30) as r:
                        state = json.load(r)
                    (d / f'{label}.json').write_text(json.dumps(state, indent=2) + '\n')
                    stacks = state['goroutine_stacks']
                    row['stages'].append({'label': label, 'next_tid': state['next_tid'],
                        'goroutines': state['goroutines'], 'waiter_count': sum(state['host_waiters'].values()),
                        'wait_addresses': len(state['host_waiters']), 'fd_count': len(state['fds']),
                        'socket_count': sum(f.get('socket', False) for f in state['fds']),
                        'page_cleaner_frame': '.Fn18163(' in stacks,
                        'atomic_wait_frames': stacks.count('AtomicWait32At(') + stacks.count('AtomicWait64At(')})

                def q(sql):
                    r = g.call(2, sql)
                    row['sql'].append({'sql': sql, 'result': r})
                    assert r['ok'], (sql, r)
                    return r

                assert g.call(1)['ok']
                assert q('SELECT COUNT(*) FROM benchmark_rows')['rows'][0][0]['$h'] == '31303030'
                q('SELECT @@in_transaction')
                status = q('SHOW ENGINE INNODB STATUS')
                (d / 'innodb-status.json').write_text(json.dumps(status, indent=2) + '\n')
                assert g.call(3)['closed']
                sample('no-client')
                # Observation interval only; no attempt to force worker ordering.
                time.sleep(2)
                sample('idle')
                assert g.call(1)['ok']
                q('FLUSH TABLES benchmark_rows FOR EXPORT')
                sample('table-export')
                q('SELECT COUNT(*) FROM benchmark_rows')
                q('UNLOCK TABLES')
                q('FLUSH TABLES WITH READ LOCK')
                sample('global-read-lock')
                q('UNLOCK TABLES')
                assert g.call(3)['closed']
                sample('unlocked-closed')
                assert g.stop() == 0
                row['completed'] = True
            except Exception as error:
                row['failure'] = str(error)
                raise
            finally:
                if g.proc.poll() is None:
                    g.proc.kill()
                    g.proc.wait()
                row['exit_code'] = g.proc.returncode
                (out / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
        print(trial, 'PASS', flush=True)


if __name__ == '__main__':
    main()
