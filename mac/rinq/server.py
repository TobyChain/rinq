from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .collectors import collect
from .config import load_config
from .dashboard import HTML
from .events import apply_event
from .focus import current_focus
from .push import push_glance
from . import sessions as sessions_mod
from .settings_api import apply_public_settings, connect_integration, public_settings
from .state import load_state, update_state
from .usage import build_usage_summary

_SESSIONS_TTL_SECONDS = 5
_sessions_cache_lock = threading.RLock()
_sessions_cache_generation = 0
_sessions_cache: tuple[int, int, dict[str, Any]] | None = None


def build_sessions(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the live agent-session snapshot, throttled to one scan per TTL."""
    global _sessions_cache
    now_ts = int(time.time())
    local_state = state
    while True:
        with _sessions_cache_lock:
            cached = _sessions_cache
            generation = _sessions_cache_generation
            if cached is not None and cached[0] == generation and now_ts - cached[1] <= _SESSIONS_TTL_SECONDS:
                return cached[2]
        snapshot_state = local_state if local_state is not None else load_state()
        snapshot = sessions_mod.build_sessions(snapshot_state, now_ts)
        with _sessions_cache_lock:
            if generation != _sessions_cache_generation:
                local_state = None
                continue
            _sessions_cache = (generation, now_ts, snapshot)
            return snapshot


def invalidate_sessions_cache() -> None:
    """Drop the cached /sessions snapshot after hook-driven lifecycle changes."""
    global _sessions_cache_generation, _sessions_cache
    with _sessions_cache_lock:
        _sessions_cache_generation += 1
        _sessions_cache = None


def build_status() -> dict[str, Any]:
    cfg = load_config()
    rings = collect(cfg)
    live = build_sessions()

    def _merge(state: dict[str, Any]) -> dict[str, Any]:
        state["rings"] = rings
        focus = current_focus(state, cfg)
        agents = dict(state.get("agents", {}))
        # Live session counts are authoritative; the persisted counters only feed
        # the daily totals when no hooks are installed.
        agents["running"] = live["counts"]["running"]
        agents["subagentsRunning"] = live["counts"].get("subagentsRunning", 0)
        agents["waiting"] = live["counts"]["waiting"]
        return {
            "version": 1,
            "updatedAt": state.get("updatedAt"),
            "rings": rings,
            "agents": agents,
            "focus": focus,
        }

    return update_state(_merge)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: Any) -> None:
        pass

    def _send_json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        # The dashboard is same-origin; local summaries must not be readable
        # by arbitrary websites or retained in browser/proxy caches.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, html: str) -> None:
        data = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send_html(HTML)
        elif path == "/status":
            self._send_json(200, build_status())
        elif path == "/config":
            self._send_json(200, public_settings(load_config()))
        elif path == "/usage":
            self._send_json(200, build_usage_summary())
        elif path == "/sessions":
            self._send_json(200, build_sessions())
        elif path == "/integrations":
            self._send_json(200, {"integrations": public_settings(load_config()).get("integrations", [])})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        if path == "/event":
            cfg = load_config()
            try:
                update_state(lambda state: apply_event(state, payload, cfg))
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            invalidate_sessions_cache()
            self._send_json(200, {"ok": True})
        elif path == "/mock":
            def _apply_mock(state: dict[str, Any]) -> None:
                state["rings"] = payload.get("rings", [])
                if "agents" in payload:
                    state["agents"] = payload["agents"]
            update_state(_apply_mock)
            self._send_json(200, {"ok": True})
        elif path == "/glance":
            cfg = load_config()
            status = build_status()
            ok = push_glance(cfg, status["rings"], status["agents"])
            self._send_json(200 if ok else 202, {"pushed": ok})
        elif path == "/config":
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                self._send_json(403, {"error": "config changes are local-only"})
                return
            cfg = load_config()
            try:
                apply_public_settings(cfg, payload)
            except (ValueError, TypeError) as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, {"ok": True, "config": public_settings(load_config())})
        elif path == "/auth/connect":
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                self._send_json(403, {"error": "authentication actions are local-only"})
                return
            integration_id = payload.get("integrationId")
            if not isinstance(integration_id, str) or not connect_integration(integration_id):
                self._send_json(404, {"error": "unknown integration"})
                return
            self._send_json(200, {"ok": True})
        else:
            self._send_json(404, {"error": "not found"})


def _local_ip() -> str:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def serve(port: int, host: str = "127.0.0.1") -> None:
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"rinq serving on http://{host}:{port}")
    if host in ("0.0.0.0", ""):
        print(f"open on this network: http://{_local_ip()}:{port}  (iPhone/iPad)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
