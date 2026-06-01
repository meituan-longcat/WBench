"""
Simple HTTP server with CORS + Private Network Access headers.
Usage: python serve.py [port] [directory]

Defaults to serving the current working directory (where you launch it from).
Run from the repo root so that data/images/... resolves correctly.
"""
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import os

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 18888
SERVE_DIR = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

class CORSHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress logs

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

print(f"Serving {SERVE_DIR} on port {PORT}")
ThreadedHTTPServer(("0.0.0.0", PORT), CORSHandler).serve_forever()
