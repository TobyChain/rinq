from __future__ import annotations

import json
import time
from typing import Any

from .config import STATE_PATH, ensure_dirs


def now() -> int:
    return int(time.time())


def blank_state() -> dict[str, Any]:
    return {
        "version": 1,
        "updatedAt": now(),
        "rings": [],
        "agents": {
            "running": 0,
            "waiting": 0,
            "doneToday": 0,
            "failedToday": 0,
            "lastEvent": None,
        },
        "focus": {"mode": "idle", "remainingMins": 0, "breakEveryMins": 50},
    }


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return blank_state()


def save_state(state: dict[str, Any]) -> None:
    ensure_dirs()
    state["updatedAt"] = now()
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_PATH)


def clamp_pct(value: float | None) -> int | None:
    if value is None:
        return None
    return max(0, min(100, int(round(value))))
