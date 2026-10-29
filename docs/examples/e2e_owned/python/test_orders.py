"""Opt-in actual Django/browser acceptance for the owned entry candidate."""
import contextlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

if os.environ.get("E2E_OWNED_RUNTIME") != "1":
    pytest.skip("set E2E_OWNED_RUNTIME=1 for actual owned browser entry", allow_module_level=True)

import MySQLdb
from playwright.sync_api import expect, sync_playwright
from mariamem.e2e import BrowserEntry, Config

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / "tests/e2e_native_control/pythonapp"


def env_for(info):
    return dict(os.environ, E2E_DB_HOST=info["host"], E2E_DB_PORT=str(info["port"]),
                E2E_DB_NAME="e2e_app", E2E_NUMERIC_HTTP_BIND="1",
                PYTHONPATH=str(ROOT / "tests/live_acceptance/diagnostics"))


def prepare(source):
    info = source.connection_info()
    with contextlib.closing(MySQLdb.connect(host=info["host"], port=info["port"],
            user=info["user"], passwd=info["password"], autocommit=True)) as c:
        with c.cursor() as cursor:
            cursor.execute("CREATE DATABASE e2e_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    subprocess.run([sys.executable, str(APP / "manage.py"), "migrate", "--noinput"],
                   env=env_for(info), check=True, timeout=60)


class App:
    def __init__(self, process, base_url):
        self.process, self.base_url = process, base_url
        self.identity = process.pid
    def quiesce_and_retire(self, ctx):
        # Sole work source is the completed previous browser case. The unchanged
        # app has no background jobs and CONN_MAX_AGE=0; Live still checks drain.
        ctx.check()
        if self.process.poll() is not None:
            raise RuntimeError("Django exited")
    def stop_reap(self, ctx):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.wait(timeout=ctx.remaining())
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
            raise RuntimeError("Django required forced shutdown")


def start_ready(ctx, info, register):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen([sys.executable, str(APP / "manage.py"), "runserver",
        "--noreload", "--nothreading", f"127.0.0.1:{port}"], env=env_for(info))
    app = App(process, f"http://127.0.0.1:{port}")
    register(app)  # ownership precedes readiness, including on the failure path
    while True:
        ctx.check()
        if process.poll() is not None:
            raise RuntimeError("Django failed before readiness")
        try:
            with urlopen(app.base_url + "/healthz", timeout=min(1, ctx.remaining())) as r:
                health = json.load(r)
            if health["pid"] != process.pid or health["db_name"] != "e2e_app":
                raise RuntimeError("wrong application identity")
            return app
        except OSError:
            time.sleep(.05)


@pytest.fixture(scope="module")
def entry():
    with BrowserEntry(Config(prepare=prepare, start_ready=start_ready,
            sole_work_source=True, options={"host_binary": os.environ["MARIAMEM_TEST_HOST"]})) as owner:
        app = owner.app
        yield owner
    assert app.process.poll() is not None


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.mark.parametrize("case_name", ["first", "second"])
def test_owned_browser_seed(entry, browser, case_name):
    with entry.case(browser=browser) as case:
        case.page.set_default_timeout(10000)
        case.page.goto(case.app.base_url + "/orders")
        expect(case.page.get_by_test_id("order")).to_have_text(["SEED:2:ready"])
        case.page.get_by_label("SKU", exact=True).fill("NEW")
        case.page.get_by_label("Quantity", exact=True).fill("3")
        case.page.get_by_role("button", name="Save", exact=True).click()
        expect(case.page.get_by_text("Order created", exact=True)).to_be_visible()
        expect(case.page.get_by_test_id("order")).to_have_text(["SEED:2:ready", "NEW:3:ready"])
