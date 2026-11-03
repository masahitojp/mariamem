"""Run from outside checkout with the installed candidate wheel and no PYTHONPATH."""
import json
from pathlib import Path
import mariamem
import pymysql


def check(source):
    session=source._session
    saved=live=None
    def connect(target):return pymysql.connect(**target.connection_info(),autocommit=True)
    try:
        with connect(source) as c:
            with c.cursor() as q:
                q.execute('CREATE TABLE live_user(n INT)');q.execute('INSERT INTO live_user VALUES(1)')
        source.wait_disconnected();saved=source.snapshot(max_forks=2)
        assert saved.max_forks == 2
        first=saved.fork(timeout=5);second=None
        try:
            with connect(first) as c:
                with c.cursor() as q:q.execute('INSERT INTO live_user VALUES(9)')
            second=saved.fork(timeout=5)
            with connect(second) as c:
                with c.cursor() as q:q.execute('SELECT SUM(n) FROM live_user');assert q.fetchone()==(1,)
            try:
                saved.fork(timeout=.03)
            except mariamem.HostError as error:
                assert error.code=='pool_timeout' and error.stage=='fork_wait'
            else:
                raise AssertionError('cap2 admitted a third child')
            with connect(first) as c:
                with c.cursor() as q:q.execute('SELECT SUM(n) FROM live_user');assert q.fetchone()==(10,)
        finally:
            if second is not None:second.close()
            first.close()
        live=saved.live();info=live.connection_info()
        with connect(live) as c:
            with c.cursor() as q:q.execute('INSERT INTO live_user VALUES(2)')
        blocker=saved.fork(timeout=5)
        try:
            try:
                live.reset()
            except mariamem.Busy as error:
                assert error.stage=='live_capacity'
            else:
                raise AssertionError('Live Reset did not reserve its spare slot')
            assert live.status()['generation']==0 and live.connection_info()==info
            with connect(live) as c:
                with c.cursor() as q:q.execute('SELECT SUM(n) FROM live_user');assert q.fetchone()==(3,)
        finally:
            blocker.close()
        live.reset()
        with connect(live) as c:
            with c.cursor() as q:q.execute('SELECT SUM(n) FROM live_user');assert q.fetchone()==(1,)
        assert live.connection_info()==info and live.status()['generation']==1
    finally:
        if live is not None:live.close()
        if saved is not None:saved.close()
        source.close()
    assert session._process.poll() is not None and not session.root.exists()
    return dict(module=str(Path(mariamem.__file__).resolve()),source_consumed=source.closed,
                host_reaped=True,directory_removed=True,max_forks=2,
                capacity_timeout_preserved=True,live_capacity_busy_preserved=True)


def main():
    print(json.dumps(dict(result='PASS_INSTALLED_PYTHON_LIVE', **check(mariamem.start()))))


if __name__=='__main__':main()
