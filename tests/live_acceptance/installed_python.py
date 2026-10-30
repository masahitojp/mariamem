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
        source.wait_disconnected();saved=source.snapshot();live=saved.live();info=live.connection_info()
        with connect(live) as c:
            with c.cursor() as q:q.execute('INSERT INTO live_user VALUES(2)')
        live.reset()
        with connect(live) as c:
            with c.cursor() as q:q.execute('SELECT SUM(n) FROM live_user');assert q.fetchone()==(1,)
        assert live.connection_info()==info and live.status()['generation']==1
    finally:
        if live is not None:live.close()
        if saved is not None:saved.close()
        source.close()
    assert session._process.poll() is not None and not session.root.exists()
    return dict(module=str(Path(mariamem.__file__).resolve()),source_consumed=source.closed,host_reaped=True,directory_removed=True)


def main():
    print(json.dumps(dict(result='PASS_INSTALLED_PYTHON_LIVE', **check(mariamem.start()))))


if __name__=='__main__':main()
