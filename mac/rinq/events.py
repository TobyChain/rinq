from __future__ import annotations

from typing import Any

from .push import push_message
from .state import now

VALID_STATES = {"started", "completed", "failed", "waiting"}


def apply_event(state: dict[str, Any], ev: dict[str, Any], cfg: dict) -> dict[str, Any]:
    es = ev.get("state", "")
    if es not in VALID_STATES:
        raise ValueError(f"invalid state {es!r}; want one of {sorted(VALID_STATES)}")
    agents = state.setdefault("agents", {})
    day = now() // 86400

    if state.get("agentsDay") != day:
        agents["doneToday"] = 0
        agents["failedToday"] = 0
        state["agentsDay"] = day

    running = int(agents.get("running", 0))
    waiting = int(agents.get("waiting", 0))
    if es == "started":
        agents["running"] = running + 1
        agents["waiting"] = max(0, waiting - 1)
    elif es == "completed":
        agents["running"] = max(0, running - 1)
        agents["waiting"] = max(0, waiting - 1)
        agents["doneToday"] = int(agents.get("doneToday", 0)) + 1
    elif es == "failed":
        agents["running"] = max(0, running - 1)
        agents["waiting"] = max(0, waiting - 1)
        agents["failedToday"] = int(agents.get("failedToday", 0)) + 1
    elif es == "waiting":
        agents["waiting"] = max(waiting, 1)

    title = str(ev.get("title", es)).strip() or es
    detail = str(ev.get("detail", "")).strip()
    agents["lastEvent"] = {"state": es, "title": title, "at": now()}

    if es in {"waiting", "failed", "completed"}:
        msg = detail or title
        push_message(cfg, f"AI {es}", f"{title}: {msg}" if detail and detail != title else title)

    return state
