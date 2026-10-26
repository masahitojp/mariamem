"""Run sequentially: one Django process, one Live endpoint, fresh DB per test."""
import contextlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import MySQLdb
import mariamem
from playwright.sync_api import expect, sync_playwright
import pytest

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / 'tests/e2e_native_control/pythonapp'
SCHEMA = 'e2e_app'


def manage(env, *args):
    subprocess.run([sys.executable, str(APP / 'manage.py'), *args], env=env,
                   check=True, timeout=60)


def health(url):
    with urlopen(url + '/healthz', timeout=1) as response:
        return json.load(response)


@pytest.fixture(scope='module')
def application(tmp_path_factory):
    """Migrate once; keep Snapshot, Live and app alive for the whole module."""
    host = os.environ['MARIAMEM_HOST_BINARY']
    with mariamem.start(host_binary=host) as source:
        info = source.connection_info()
        with contextlib.closing(MySQLdb.connect(
                host=info['host'], port=info['port'], user=info['user'],
                passwd=info['password'], autocommit=True)) as connection:
            with connection.cursor() as cursor:
                cursor.execute('CREATE DATABASE e2e_app CHARACTER SET utf8mb4 '
                               'COLLATE utf8mb4_unicode_ci')
        env = dict(os.environ, E2E_DB_HOST=info['host'],
                   E2E_DB_PORT=str(info['port']), E2E_DB_NAME=SCHEMA)
        manage(env, 'migrate', '--noinput')
        source.wait_disconnected()
        with source.snapshot() as prepared, prepared.live() as live:
            env['E2E_DB_PORT'] = str(live.connection_info()['port'])
            # Reuse the numeric-bind harness already exercised by acceptance.
            # It avoids reverse DNS for the explicit 127.0.0.1 HTTP identity.
            env['PYTHONPATH'] = os.pathsep.join([
                str(ROOT / 'tests/live_acceptance/diagnostics'),
                os.environ.get('PYTHONPATH', ''),
            ])
            env['E2E_NUMERIC_HTTP_BIND'] = '1'
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            url = f'http://127.0.0.1:{port}'
            log_path = tmp_path_factory.mktemp('django-live') / 'server.txt'
            with log_path.open('w') as log:
                app = subprocess.Popen([
                    sys.executable, str(APP / 'manage.py'), 'runserver',
                    '--noreload', '--nothreading', f'127.0.0.1:{port}',
                ], env=env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 30
                    while True:
                        if app.poll() is not None or time.monotonic() >= deadline:
                            pytest.fail('Django startup failed:\n' + log_path.read_text())
                        try:
                            observed = health(url)
                            assert observed['pid'] == app.pid
                            assert observed['db_name'] == SCHEMA
                            break
                        except OSError:
                            time.sleep(.05)
                    yield live, url, app
                finally:
                    if app.poll() is None:
                        app.terminate()
                    try:
                        app.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        app.kill()
                        app.wait(timeout=5)
                    # The app must exit before Live and Snapshot are closed.
                    assert app.poll() is not None


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(application, browser):
    live, url, app = application
    assert app.poll() is None
    # Previous browser context has closed and all requests completed. Django's
    # CONN_MAX_AGE=0 releases physical DB sessions at each request boundary.
    live.reset(timeout=120, drain_timeout=5)
    assert health(url)['pid'] == app.pid
    with browser.new_context() as context:
        page = context.new_page()
        page.set_default_timeout(10000)
        page.goto(url + '/orders')
        expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready'])
        yield page


@pytest.mark.parametrize('case', ['first', 'second'])
def test_create_order_from_fresh_baseline(page, case):
    # Reusing the same UNIQUE SKU makes leaked data visible on the next case.
    page.get_by_label('SKU', exact=True).fill('NEW')
    page.get_by_label('Quantity', exact=True).fill('3')
    page.get_by_role('button', name='Save', exact=True).click()
    expect(page.get_by_text('Order created', exact=True)).to_be_visible()
    expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready', 'NEW:3:ready'])
