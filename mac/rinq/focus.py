from __future__ import annotations

import time
from typing import Any

from .state import now


def current_focus(state: dict[str, Any], cfg: dict) -> dict[str, Any]:
    break_every = int(cfg.get("focus", {}).get("breakEveryMins", 50))
    focus = state.get("focus", {})
    started = focus.get("startedAt")
    mode = focus.get("mode", "idle")
    if mode != "focus" or not started:
        return {"mode": "idle", "remainingMins": 0, "breakEveryMins": break_every}
    elapsed = (now() - int(started)) // 60
    remaining = max(0, break_every - int(elapsed))
    return {
        "mode": "break" if remaining == 0 else "focus",
        "remainingMins": int(remaining),
        "breakEveryMins": break_every,
    }


def start_focus(state: dict[str, Any]) -> dict[str, Any]:
    state["focus"] = {"mode": "focus", "startedAt": int(time.time()), "remainingMins": 0}
    return state
