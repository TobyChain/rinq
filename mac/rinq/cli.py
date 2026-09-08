from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

from . import __version__
from .config import DEFAULT_PORT, load_config
from .focus import start_focus
from .server import build_status, serve
from .state import load_state, save_state


def _post(path: str, payload: dict) -> dict[str, Any]:
    cfg = load_config()
    url = f"http://127.0.0.1:{cfg.get('port', DEFAULT_PORT)}{path}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(build_status(), indent=2, ensure_ascii=False))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    cfg = load_config()
    serve(args.port or cfg.get("port", DEFAULT_PORT))
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    ev = {"source": args.source or "cli", "state": args.state, "title": args.title}
    if args.detail:
        ev["detail"] = args.detail
    try:
        _post("/event", ev)
    except (urllib.error.URLError, ConnectionError):
        # Daemon not running: apply directly to state so the command still works.
        from .events import apply_event

        cfg = load_config()
        state = load_state()
        apply_event(state, ev, cfg)
        save_state(state)
    print(f"recorded: {args.state} — {args.title}")
    return 0


def cmd_focus(_args: argparse.Namespace) -> int:
    state = load_state()
    start_focus(state)
    save_state(state)
    print("focus session started (50m countdown; watch break event at 0)")
    return 0


def cmd_hook_traex(_args: argparse.Namespace) -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    event = payload.get("hook_event_name") or payload.get("event_type") or ""
    ev: dict[str, Any] = {"source": "traex"}
    if event == "Stop":
        ev.update(state="completed", title="TraeX turn complete")
    elif event == "Notification":
        ntype = payload.get("notification_type", "")
        if "permission" in ntype:
            ev.update(state="waiting", title="TraeX needs approval")
        else:
            ev.update(state="waiting", title="TraeX is waiting")
    elif event == "SessionStart":
        ev.update(state="started", title=f"TraeX session {payload.get('source', 'start')}")
    else:
        return 0
    try:
        _post("/event", ev)
    except Exception:
        pass
    return 0


def cmd_hook_codex(args: argparse.Namespace) -> int:
    payload_raw = getattr(args, "payload", "") or ""
    if not payload_raw:
        return 0
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return 0
    if payload.get("type") != "agent-turn-complete":
        return 0
    title = "Codex turn complete"
    ev = {
        "source": "codex",
        "state": "completed",
        "title": title,
        "detail": str(payload.get("last-assistant-message", ""))[:200],
    }
    try:
        _post("/event", ev)
    except Exception:
        pass
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rinq", description="AI quota rings for Apple Watch")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="print aggregated status JSON")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("serve", help="run the local HTTP API")
    s.add_argument("--port", type=int, default=0)
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser("push", help="record an agent event")
    s.add_argument("--state", required=True, choices=["started", "completed", "failed", "waiting"])
    s.add_argument("--title", required=True)
    s.add_argument("--detail", default="")
    s.add_argument("--source", default="cli")
    s.set_defaults(func=cmd_push)

    s = sub.add_parser("focus", help="start a 50m focus countdown")
    s.set_defaults(func=cmd_focus)

    s = sub.add_parser("hook-traex", help="read a TraeX hook payload from stdin")
    s.set_defaults(func=cmd_hook_traex)

    s = sub.add_parser("hook-codex", help="read a Codex notify payload (JSON arg)")
    s.add_argument("payload", nargs="?", default="")
    s.set_defaults(func=cmd_hook_codex)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
