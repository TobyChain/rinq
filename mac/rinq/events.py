from __future__ import annotations

from typing import Any

from .push import push_message
from .state import now

VALID_STATES = {
    "started", "running", "subagents_running", "waiting", "idle",
    "completed", "failed", "closed",
}


def _event_title(app: str, state_name: str) -> str:
    """Return a privacy-safe persisted label for an agent lifecycle event."""
    subject = app or "Agent"
    caption = {
        "started": "started",
        "running": "is running",
        "subagents_running": "subagents running",
        "waiting": "waiting",
        "idle": "is idle",
        "completed": "completed",
        "failed": "failed",
        "closed": "closed",
    }[state_name]
    return f"{subject} {caption}"


def apply_event(state: dict[str, Any], ev: dict[str, Any], cfg: dict) -> dict[str, Any]:
    """Apply one external agent event to persisted daemon state."""
    es = ev.get("state", "")
    if es not in VALID_STATES:
        raise ValueError(f"invalid state {es!r}; want one of {sorted(VALID_STATES)}")
    session_id = str(ev.get("sessionId") or "").strip()
    closed_sessions = state.setdefault("closedSessions", {})
    if session_id and es not in {"started", "closed"} and session_id in closed_sessions:
        return state
    agents = state.setdefault("agents", {})
    day = now() // 86400

    if state.get("agentsDay") != day:
        agents["doneToday"] = 0
        agents["failedToday"] = 0
        state["agentsDay"] = day

    agents.setdefault("subagentsRunning", 0)
    running = int(agents.get("running", 0))
    waiting = int(agents.get("waiting", 0))
    subagents_running = int(agents.get("subagentsRunning", 0))
    if es in {"started", "running", "subagents_running"}:
        agents["running"] = running + 1
        agents["waiting"] = max(0, waiting - 1)
        if es == "subagents_running":
            agents["subagentsRunning"] = subagents_running + 1
    elif es in {"completed", "idle", "closed"}:
        agents["running"] = max(0, running - 1)
        agents["waiting"] = max(0, waiting - 1)
        agents["subagentsRunning"] = max(0, subagents_running - 1)
        if es in {"completed", "idle"}:
            agents["doneToday"] = int(agents.get("doneToday", 0)) + 1
    elif es == "failed":
        agents["running"] = max(0, running - 1)
        agents["waiting"] = max(0, waiting - 1)
        agents["subagentsRunning"] = max(0, subagents_running - 1)
        agents["failedToday"] = int(agents.get("failedToday", 0)) + 1
    elif es == "waiting":
        agents["waiting"] = max(waiting, 1)

    app = str(ev.get("app") or ev.get("source") or "").strip()
    title = str(ev.get("title", "")).strip()
    detail = str(ev.get("detail", "")).strip()
    event_at = now()
    agents["lastEvent"] = {"state": es, "title": _event_title(app, es), "at": event_at}

    sessions = state.setdefault("agentSessions", {})
    if session_id and es == "closed":
        sessions.pop(session_id, None)
        closed_sessions[session_id] = event_at
        for sid in [sid for sid, at in closed_sessions.items() if event_at - int(at or 0) > 86400]:
            closed_sessions.pop(sid, None)
    elif session_id:
        if es == "started":
            closed_sessions.pop(session_id, None)
        existing = sessions.get(session_id, {})
        current_subagents = int(existing.get("subagentCount", 0) or 0) if isinstance(existing, dict) else 0
        record_state = es
        record_subagents = 0
        if es == "subagents_running":
            record_subagents = max(1, current_subagents + 1)
        elif es == "running" and current_subagents > 1:
            record_state = "subagents_running"
            record_subagents = current_subagents - 1
        for field in ("cwd", "model"):
            value = str(ev.get(field) or "").strip()
            if value:
                existing[field] = value
        record = {
            "state": record_state,
            "app": app,
            "at": event_at,
        }
        if record_subagents:
            record["subagentCount"] = record_subagents
        for field in ("cwd", "model"):
            if existing.get(field):
                record[field] = existing[field]
        sessions[session_id] = record
        # Drop hook records older than a day so the overlay cannot grow without
        # bound; build_sessions applies shorter per-state TTLs on read.
        for sid in [sid for sid, rec in sessions.items() if event_at - int(rec.get("at", 0)) > 86400]:
            sessions.pop(sid, None)

    if es in {"waiting", "failed", "completed"}:
        msg = detail or title
        push_message(cfg, f"AI {es}", f"{title}: {msg}" if detail and detail != title else title)

    return state
