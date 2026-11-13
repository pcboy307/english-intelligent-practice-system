from __future__ import annotations

import argparse
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


def resolve_static_path(web_root: str | Path, url_path: str) -> Path | None:
    root = Path(web_root).resolve()
    decoded = unquote(urlsplit(url_path).path)
    relative = decoded.lstrip("/")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_file():
        return candidate
    if candidate.suffix:
        return None
    index = root / "index.html"
    return index if index.is_file() else None


def make_handler(web_root: Path):
    class SpaHandler(BaseHTTPRequestHandler):
        server_version = "GaoerEnglishWeb/1.0"

        def do_HEAD(self) -> None:
            self._serve(send_body=False)

        def do_GET(self) -> None:
            self._serve(send_body=True)

        def _serve(self, *, send_body: bool) -> None:
            target = resolve_static_path(web_root, self.path)
            if target is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content = target.read_bytes()
            content_type = (
                mimetypes.guess_type(target.name)[0]
                or "application/octet-stream"
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            if target.name == "index.html":
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "public, max-age=31536000")
            self.end_headers()
            if send_body:
                self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            print(
                f"{self.address_string()} - {format % args}",
                flush=True,
            )

    return SpaHandler


def serve(web_root: Path, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(web_root))
    print(f"serving {web_root} on http://{host}:{port}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    serve(Path(args.root), args.host, args.port)


if __name__ == "__main__":
    main()
