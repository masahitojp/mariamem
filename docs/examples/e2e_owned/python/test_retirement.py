"""Real Python SQL/Live drain with an explicitly controlled app hook."""
import contextlib
import os

import pytest

if os.environ.get("E2E_OWNED_RUNTIME") != "1":
    pytest.skip("explicit owned runtime only", allow_module_level=True)

import MySQLdb
import test_orders as example
from mariamem.e2e import BrowserEntry, Config, EntryError

browser = example.browser


def connect(info):
    return MySQLdb.connect(host=info["host"], port=info["port"],
                           user=info["user"], passwd=info["password"],
                           db=info["database"], autocommit=True)


def prepare(source):
    with contextlib.closing(connect(source.connection_info())) as c:
        with c.cursor() as cursor:
            cursor.execute("CREATE TABLE entry_seed (sku VARCHAR(32) PRIMARY KEY)")
            cursor.execute("INSERT INTO entry_seed VALUES ('SEED')")


class App:
    identity, base_url = "controlled-python-sql-owner", "http://127.0.0.1:1"

    def __init__(self, info, retire):
        self.info, self.retire = info, retire
        self.client = connect(info)
        self.stopped = False

    def quiesce_and_retire(self, ctx):
        ctx.check()
        if self.retire and self.client is not None:
            self.client.close()
            self.client = None
        # Negative control returns success while retaining a physical session.

    def stop_reap(self, ctx):
        ctx.check()
        if self.client is not None:
            self.client.close()
            self.client = None
        self.stopped = True


def config(retire):
    def start(ctx, info, register):
        app = App(info, retire)
        register(app)
        return app
    return Config(prepare=prepare, start_ready=start, sole_work_source=True,
                  drain_timeout=.1, options={"host_binary": os.environ["MARIAMEM_TEST_HOST"]})


def test_lying_hook_cannot_bypass_physical_drain():
    with BrowserEntry(config(False)) as owner:
        app = owner.app
        with pytest.raises(EntryError) as caught:
            with owner.case(browser=None):
                pytest.fail("busy setup admitted body")
        assert caught.value.stage == "reset"
        assert caught.value.__cause__.code == "busy"
        assert owner._live.status()["generation"] == 0
        with pytest.raises(EntryError) as later:
            with owner.case(browser=None):
                pytest.fail("later body admitted")
        assert later.value.stage == "case_admission"
    assert app.stopped and app.client is None


def test_physical_retirement_restores_seed_and_closes_browser_context(browser):
    with BrowserEntry(config(True)) as owner:
        app = owner.app
        for generation in (1, 2):
            with owner.case(browser=browser) as case:
                page = case.page
                with contextlib.closing(connect(app.info)) as c:
                    with c.cursor() as cursor:
                        cursor.execute("SELECT sku FROM entry_seed ORDER BY sku")
                        assert cursor.fetchall() == (("SEED",),)
                        cursor.execute("INSERT INTO entry_seed VALUES ('NEW')")
                assert owner._live.status()["generation"] == generation
            assert page.is_closed()
    assert app.stopped and app.client is None
