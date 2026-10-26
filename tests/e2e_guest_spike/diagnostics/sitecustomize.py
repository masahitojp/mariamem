"""Opt-in E2E child harness; never imported by the product SDK."""
import os

if os.environ.get('E2E_NUMERIC_HTTP_BIND') == '1':
    import http.server
    import socket
    import socketserver
    import sys

    _original_server_bind = http.server.HTTPServer.server_bind

    def _numeric_loopback_bind(server):
        if server.address_family != socket.AF_INET or server.server_address[0] != '127.0.0.1':
            return _original_server_bind(server)
        socketserver.TCPServer.server_bind(server)
        server.server_name, server.server_port = server.server_address[:2]
        print(f'E2E_NUMERIC_HTTP_BIND address={server.server_name} port={server.server_port}',
              file=sys.stderr, flush=True)

    # HTTPServer normally reverse-resolves the bound IP for SERVER_NAME.
    # This harness uses an explicit loopback identity and preserves WSGIServer's
    # subsequent setup_environ(), including the actual allocated SERVER_PORT.
    http.server.HTTPServer.server_bind = _numeric_loopback_bind

if os.environ.get('E2E_CHILD_DIAGNOSTICS') == '1':
    import faulthandler
    import sys

    print(f'E2E_CHILD_DIAGNOSTICS pid={os.getpid()} python={sys.version}',
          file=sys.stderr, flush=True)
    # Two stack snapshots fit inside the unchanged 30-second app startup gate.
    # The process owns this timer; it changes no SQL, app checks or timeouts.
    faulthandler.enable()
    faulthandler.dump_traceback_later(10, repeat=True)
