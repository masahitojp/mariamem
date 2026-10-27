"""Real WSGI HTTP request with a deliberately unusable reverse resolver."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


PROGRAM='''
import json, socket, threading
from urllib.request import urlopen
from wsgiref.simple_server import make_server

def broken_reverse_dns(host):
    raise RuntimeError('E2E_REVERSE_DNS_MUST_NOT_RUN')
socket.getfqdn = broken_reverse_dns

def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'application/json')])
    return [json.dumps({k: environ[k] for k in ['SERVER_NAME', 'SERVER_PORT']}).encode()]

with make_server('127.0.0.1', 0, app) as server:
    worker = threading.Thread(target=server.handle_request, daemon=True)
    worker.start()
    with urlopen(f'http://127.0.0.1:{server.server_port}/healthz', timeout=2) as response:
        observed = json.load(response)
    worker.join(timeout=2)
    assert not worker.is_alive()
    assert observed == {'SERVER_NAME': '127.0.0.1', 'SERVER_PORT': str(server.server_port)}
    print(json.dumps(observed))
'''


class NumericBind(unittest.TestCase):
    def run_child(self, enabled, program=PROGRAM):
        directory=Path(__file__).parent/'live_acceptance/diagnostics'
        env=dict(os.environ,PYTHONPATH=str(directory),E2E_NUMERIC_HTTP_BIND=enabled,E2E_CHILD_DIAGNOSTICS='0')
        return subprocess.run([sys.executable,'-c',program],env=env,capture_output=True,text=True,timeout=10)

    def test_real_wsgi_request_succeeds_despite_broken_reverse_dns(self):
        result=self.run_child('1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['SERVER_NAME'],'127.0.0.1')
        self.assertIn('E2E_NUMERIC_HTTP_BIND address=127.0.0.1',result.stderr)

    def test_without_workaround_the_same_resolver_defect_is_detected(self):
        result=self.run_child('0')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('E2E_REVERSE_DNS_MUST_NOT_RUN',result.stderr)

    def test_hostname_binding_keeps_original_resolution(self):
        result=self.run_child('1','''
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
socket.getfqdn = lambda host: 'resolved-test-host'
with HTTPServer(('localhost',0),BaseHTTPRequestHandler) as server:
    assert server.server_name == 'resolved-test-host'
print('original resolver retained')
''')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout,'original resolver retained\n')
        self.assertNotIn('E2E_NUMERIC_HTTP_BIND',result.stderr)


if __name__=='__main__':unittest.main()
