#!/usr/bin/env python3
"""Simple HTTP server for the mech scene."""
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8129
DIRECTORY = sys.argv[2] if len(sys.argv) > 2 else 'C:/æ/site/aipodcast_me'

os.chdir(DIRECTORY)
handler = SimpleHTTPRequestHandler
httpd = HTTPServer(('127.0.0.1', PORT), handler)
print(f'Serving HTTP on 127.0.0.1 port {PORT} (http://127.0.0.1:{PORT}/) from {os.getcwd()}', flush=True)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
httpd.server_close()
