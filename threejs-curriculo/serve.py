#!/usr/bin/env python3
"""Simple HTTP server for Three.js content."""
import http.server
import socketserver
import os

PORT = 8123
DIRECTORY = r"C:\æ\threejs-curriculo"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def log_message(self, format, *args):
        pass  # Suppress logs

class Server(socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

with Server(("127.0.0.1", PORT), Handler) as httpd:
    print(f"Serving {DIRECTORY} at http://127.0.0.1:{PORT}")
    httpd.serve_forever()
