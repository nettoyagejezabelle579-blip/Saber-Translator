"""Small HTTP file server with byte-range support, for the updater test.

Usage: range_server.py DIRECTORY PORT LOG_FILE
Every ranged request is logged as "<file name> <start offset>".
"""

from __future__ import annotations

import http.server
import os
import re
import sys
from functools import partial


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    log_file = ""

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            self.send_error(404)
            return None
        size = os.path.getsize(path)
        match = re.fullmatch(r"bytes=(\d+)-", self.headers.get("Range", ""))
        start = int(match.group(1)) if match else 0
        if start >= size and size:
            self.send_error(416)
            return None
        handle = open(path, "rb")
        handle.seek(start)
        if match:
            with open(self.log_file, "a", encoding="utf-8") as log:
                log.write(f"{os.path.basename(path)} {start}\n")
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{size - 1}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size - start))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        return handle


def main() -> None:
    directory, port, log_file = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    RangeHandler.log_file = log_file
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), partial(RangeHandler, directory=directory))
    server.serve_forever()


if __name__ == "__main__":
    main()
