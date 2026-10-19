from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from typing import Any

from .config import STATE_PATH, ensure_dirs


STATE_LOCK = threading.RLock()


def now() -> int:
    return int(time.time())


def blank_state() -> dict[str, Any]:
    return {
        "version": 1,
        "updatedAt": now(),
        "rings": [],
        "agents": {
            "running": 0,
            "subagentsRunning": 0,
            "waiting": 0,
            "doneToday": 0,
            "failedToday": 0,
            "lastEvent": None,
        },
        "agentSessions": {},
        "closedSessions": {},
        "focus": {"mode": "idle", "remainingMins": 0, "breakEveryMins": 50},
    }


def load_state() -> dict[str, Any]:
    with STATE_LOCK:
        return _load_state_unlocked()


def save_state(state: dict[str, Any]) -> None:
    with STATE_LOCK:
        _save_state_unlocked(state)


def update_state(mutator: Callable[[dict[str, Any]], Any]) -> Any:
    """Load, mutate, and persist daemon state under one shared lock."""
    with STATE_LOCK:
        state = _load_state_unlocked()
        result = mutator(state)
        _save_state_unlocked(state)
        return result


def _load_state_unlocked() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return blank_state()


def _save_state_unlocked(state: dict[str, Any]) -> None:
    ensure_dirs()
    state["updatedAt"] = now()
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_PATH)


def clamp_pct(value: float | None) -> int | None:
    if value is None:
        return None
    return max(0, min(100, int(round(value))))
