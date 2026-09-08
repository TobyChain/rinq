from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .collectors import collect
from .config import load_config
from .events import apply_event
from .focus import current_focus
from .push import push_glance
from .state import load_state, save_state

_last_glance = 0.0


def build_status() -> dict[str, Any]:
    cfg = load_config()
    state = load_state()
    rings = collect(cfg)
    focus = current_focus(state, cfg)
    status = {
        "version": 1,
        "updatedAt": state.get("updatedAt"),
        "rings": rings,
        "agents": state.get("agents", {}),
        "focus": focus,
    }
    state["rings"] = rings
    save_state(state)
    return status


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: Any) -> None:
        pass

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/status":
            self._send(200, build_status())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
            return

        cfg = load_config()
        state = load_state()

        if path == "/event":
            try:
                state = apply_event(state, payload, cfg)
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
                return
            save_state(state)
            self._send(200, {"ok": True})
        elif path == "/mock":
            state["rings"] = payload.get("rings", [])
            if "agents" in payload:
                state["agents"] = payload["agents"]
            save_state(state)
            self._send(200, {"ok": True})
        elif path == "/glance":
            status = build_status()
            ok = push_glance(cfg, status["rings"], status["agents"])
            self._send(200 if ok else 202, {"pushed": ok})
        else:
            self._send(404, {"error": "not found"})


def serve(port: int) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"rinq serving on http://127.0.0.1:{port}")
    httpd.serve_forever()
