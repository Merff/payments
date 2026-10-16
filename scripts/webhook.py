from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        print(self.rfile.read(int(self.headers["Content-Length"])).decode(), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


HTTPServer(("", 8099), Handler).serve_forever()
