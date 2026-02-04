from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(__file__).resolve().parent
WEB_ROOT = REPO_ROOT / "web_gui"
INDEX_PATH = WEB_ROOT / "index.html"


class WebGuiHandler(BaseHTTPRequestHandler):
    server_version = "LuraphWebGui/1.0"

    def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, payload: str) -> None:
        body = payload.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_request_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        if self.path not in {"/", "/index.html"}:
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        try:
            html = INDEX_PATH.read_text(encoding="utf-8")
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "index.html missing")
            return
        self._send_html(html)

    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        if self.path != "/deobfuscate":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        payload = self._read_request_json()
        source = str(payload.get("source") or "")
        script_key = str(payload.get("script_key") or "").strip()
        if not source.strip():
            self._send_json({"ok": False, "error": "No source provided."}, status=HTTPStatus.BAD_REQUEST)
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "input.lua"
            temp_path.write_text(source, encoding="utf-8")
            cmd = [
                sys.executable,
                str(REPO_ROOT / "main.py"),
                "--format",
                "lua",
                "--no-report",
                "--no-execute-output",
                "--force",
                str(temp_path),
            ]
            if script_key:
                cmd.extend(["--script-key", script_key])
            result = subprocess.run(
                cmd,
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )

        response = {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "output": result.stdout,
            "stderr": result.stderr,
        }
        self._send_json(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Luraph deobfuscator web GUI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on.")
    args = parser.parse_args()

    if not INDEX_PATH.exists():
        raise SystemExit(f"Missing {INDEX_PATH}; did you checkout the web_gui folder?")

    server = ThreadingHTTPServer((args.host, args.port), WebGuiHandler)
    print(f"Listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
