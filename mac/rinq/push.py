from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

GLANCES_URL = "https://api.pushover.net/1/glances.json"
MESSAGES_URL = "https://api.pushover.net/1/messages.json"

# Subtitle counts are tiny; the glance call is throttled by the caller.
_PUSH_STATES = {"waiting", "failed", "completed"}


def _post(url: str, fields: dict[str, str]) -> dict[str, Any]:
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def push_glance(cfg: dict, rings: list[dict], agents: dict) -> bool:
    p = cfg.get("push", {})
    token, user = p.get("pushoverToken", ""), p.get("pushoverUser", "")
    if not token or not user:
        return False
    codex = next((r for r in rings if r.get("id") == "codex-5h"), None)
    pct = codex.get("usedPercent") if codex else None
    fields = {
        "token": token,
        "user": user,
        "title": "Rinq",
        "text": f"{agents.get('running', 0)} run · {agents.get('waiting', 0)} wait · {agents.get('doneToday', 0)} done",
        "subtext": _subtext(rings),
    }
    if isinstance(pct, int):
        fields["percent"] = str(pct)
    try:
        _post(GLANCES_URL, fields)
        return True
    except Exception:
        return False


def push_message(cfg: dict, title: str, message: str) -> bool:
    p = cfg.get("push", {})
    token, user = p.get("pushoverToken", ""), p.get("pushoverUser", "")
    if not token or not user:
        return False
    try:
        _post(MESSAGES_URL, {"token": token, "user": user, "title": title, "message": message})
        return True
    except Exception:
        return False


def _subtext(rings: list[dict]) -> str:
    parts = []
    for r in rings[:3]:
        pct = r.get("usedPercent")
        if isinstance(pct, int):
            parts.append(f"{r.get('label', r.get('id'))} {pct}%")
    return " · ".join(parts)[:100]


def should_push(state: str) -> bool:
    return state in _PUSH_STATES
