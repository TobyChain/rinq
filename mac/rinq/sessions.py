"""Live overview of local terminal-agent sessions.

Rinq watches the same JSONL transcripts it indexes for token usage and derives
per-session state (running / subagents_running / waiting / idle) plus a short
one-line summary. Closed and completed sessions are filtered from the result.
Summaries are rebuilt in memory on every request: prompt and assistant text is
never persisted to disk or to the SQLite usage index.

Hook-reported state (``POST /event`` with a ``sessionId``) overlays the
log-derived state so approval prompts are reported exactly instead of being
inferred from transcript timing.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .config import load_config
from .usage import UsageSource, _json, _session_identity, _timestamp, discover_sources

# Only sessions touched within this window are reported.
RECENT_SECONDS = 24 * 3600
# A transcript modified within the grace window is treated as actively running.
RUNNING_GRACE_SECONDS = 120
# Shell commands legitimately run for minutes; other open tool calls are
# treated as pending approval once the short grace window passes.
BASH_GRACE_SECONDS = 15 * 60
# Keep an idle transcript visible briefly when no SessionEnd hook is installed.
# A live hook marks an idle session open for as long as its hook TTL remains.
IDLE_VISIBLE_SECONDS = 10 * 60
MAX_SESSIONS = 40
MAX_OPEN_SESSIONS = 12
TAIL_BYTES = 96 * 1024
MAX_TAIL_ENTRIES = 80
SUMMARY_LIMIT = 160

# ZCode logs do not follow the session transcript shapes below, so they stay
# usage-only.
SESSION_ADAPTERS = {"codex", "traex", "claude_code", "omp", "pi"}
OPEN_STATES = {"running", "subagents_running", "waiting", "idle"}
_STATE_RANK = {"running": 0, "subagents_running": 1, "waiting": 2, "idle": 3}
_APP_RANK = {"claude_code": 0, "codex": 1, "traex": 2, "omp": 3, "pi": 4}
_SUBAGENT_TOOLS = {"Task", "Agent", "spawn_agent", "subagent"}

# Claude Code wraps slash commands and shell IO in transcript-only tags that
# carry no readable meaning; strip tags and their contents before summarizing.
_CLAUDE_NOISE_TAGS = (
    "command-name", "command-message", "command-args",
    "local-command-stdout", "local-command-stderr",
    "bash-input", "bash-stdout", "bash-stderr",
    "file-added", "file-changed",
)
_CLAUDE_NOISE_BLOCK_RE = re.compile(
    r"<(" + "|".join(_CLAUDE_NOISE_TAGS) + r")(?:\s[^>]*)?>.*?</\1>",
    re.DOTALL,
)
_CLAUDE_NOISE_TAG_RE = re.compile(
    r"</?(?:" + "|".join(_CLAUDE_NOISE_TAGS) + r")(?:\s[^>]*)?>"
)


def _clean_claude_text(text: str) -> str:
    without_blocks = _CLAUDE_NOISE_BLOCK_RE.sub(" ", text)
    return " ".join(_CLAUDE_NOISE_TAG_RE.sub(" ", without_blocks).split())

HOOK_TTL_SECONDS = {
    "started": 5 * 60,
    "running": 5 * 60,
    "subagents_running": 5 * 60,
    "waiting": 10 * 60,
    "idle": 10 * 60,
    "completed": 60 * 60,
    "failed": 60 * 60,
}

_APP_LABEL = {
    "claude_code": "Claude Code",
    "codex": "Codex CLI",
    "traex": "TraeX",
    "omp": "OMP",
    "pi": "Pi",
}
_BASH_TOOLS = {"Bash", "shell", "exec_command", "run_command"}


@dataclass
class _Tail:
    first: dict[str, Any] | None
    entries: list[dict[str, Any]]  # chronological order, newest tail only


def session_sources(extra_sources: list[dict[str, str]] | None = None) -> list[UsageSource]:
    """Return discovered usage roots whose adapter has a session parser."""
    return [s for s in discover_sources(extra_sources) if s.adapter in SESSION_ADAPTERS]


def build_sessions(state: dict[str, Any] | None = None, now_ts: int | None = None) -> dict[str, Any]:
    """Scan recent transcripts and merge hook-reported live state."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    cfg = load_config()
    usage_cfg = cfg.get("usage")
    extra = usage_cfg.get("extraSources") if isinstance(usage_cfg, dict) else None
    cutoff = now_ts - RECENT_SECONDS

    scanned: dict[str, dict[str, Any]] = {}
    closed_sessions = state.get("closedSessions", {}) if isinstance(state, dict) else {}
    if not isinstance(closed_sessions, dict):
        closed_sessions = {}
    for adapter, root, path, mtime in _recent_candidates(extra if isinstance(extra, list) else None, cutoff):
        session = _parse_file(adapter, root, path, mtime, now_ts)
        if session is None or session["id"] in closed_sessions:
            continue
        current = scanned.get(session["id"])
        if current is None or int(session.get("updatedAt", 0)) >= int(current.get("updatedAt", 0)):
            scanned[session["id"]] = session

    sessions = dict(scanned)
    for session_id, hook in _live_hooks(state or {}, now_ts):
        existing = scanned.get(session_id)
        record = _hook_session(session_id, hook)
        if existing is None:
            if hook.get("at", 0) >= cutoff:
                sessions[session_id] = record
            continue
        # Hooks carry exact approval/lifecycle state; trust them while fresh.
        if int(hook.get("at", 0)) >= int(existing.get("updatedAt", 0)) - RUNNING_GRACE_SECONDS:
            merged = dict(existing)
            merged["state"] = record["state"]
            merged["isOpen"] = record["isOpen"]
            merged["subagentCount"] = record.get("subagentCount", 0)
            if not merged.get("summary") and record.get("summary"):
                merged["summary"] = record["summary"]
            if record.get("app"):
                merged["app"] = record["app"]
            if record.get("cwd") and not merged.get("cwd"):
                merged["cwd"] = record["cwd"]
                merged["project"] = Path(record["cwd"]).name or merged.get("project")
            merged["source"] = "hook"
            sessions[session_id] = merged

    visible = [
        session for session in sessions.values()
        if session.get("isOpen") is True and session.get("state") in OPEN_STATES
    ]
    ordered = sorted(
        visible,
        key=lambda s: (
            _APP_RANK.get(str(s.get("adapter")), 99),
            str(s.get("app") or ""),
            _STATE_RANK.get(str(s.get("state")), 9),
            str(s.get("project") or ""),
            -int(s.get("updatedAt", 0)),
        ),
    )[:MAX_OPEN_SESSIONS]

    agents = (state or {}).get("agents", {})
    counts = {
        "running": sum(1 for s in ordered if s["state"] == "running"),
        "subagentsRunning": sum(1 for s in ordered if s["state"] == "subagents_running"),
        "waiting": sum(1 for s in ordered if s["state"] == "waiting"),
        "idle": sum(1 for s in ordered if s["state"] == "idle"),
        "active": sum(1 for s in ordered if s["state"] in ("running", "subagents_running", "waiting")),
        "open": len(ordered),
        "doneToday": int(agents.get("doneToday", 0) or 0),
        "failedToday": int(agents.get("failedToday", 0) or 0),
    }
    return {"version": 1, "updatedAt": now_ts, "sessions": ordered, "counts": counts}


# --------------------------------------------------------------------------- #
# Transcript parsing
# --------------------------------------------------------------------------- #


def _parse_file(
    adapter: str, root: Path, path: Path, mtime: int, now_ts: int
) -> dict[str, Any] | None:
    try:
        tail = _read_tail(path)
    except OSError:
        return None
    if adapter == "claude_code":
        return _parse_claude(tail, path, mtime, now_ts)
    if adapter in ("codex", "traex"):
        return _parse_codex_compatible(adapter, tail, root, path, mtime, now_ts)
    if adapter in ("omp", "pi"):
        return _parse_message_log(adapter, tail, root, path, mtime, now_ts)
    return None


def _read_tail(path: Path) -> _Tail:
    size = path.stat().st_size
    with path.open("rb") as stream:
        first_line = stream.readline()
        first = _json(first_line)
        stream.seek(max(0, size - TAIL_BYTES))
        raw = stream.read()
    lines = raw.splitlines()
    if size > TAIL_BYTES and lines:
        lines = lines[1:]  # drop a line split in the middle
    entries: list[dict[str, Any]] = []
    for line in lines[-MAX_TAIL_ENTRIES:]:
        obj = _json(line)
        if obj is not None:
            entries.append(obj)
    return _Tail(first=first, entries=entries)


def _recent_candidates(
    extra_sources: list[dict[str, str]] | None, cutoff: int
) -> list[tuple[str, Path, Path, int]]:
    """Return the newest transcript candidates across all supported session roots."""
    candidates: list[tuple[int, str, Path, Path]] = []
    for source in session_sources(extra_sources):
        for path in source.root.rglob("*.jsonl"):
            try:
                mtime = int(path.stat().st_mtime)
            except OSError:
                continue
            if mtime >= cutoff:
                candidates.append((mtime, source.adapter, source.root, path))
    candidates.sort(key=lambda item: (item[0], str(item[3])), reverse=True)
    return [(adapter, root, path, mtime) for mtime, adapter, root, path in candidates[:MAX_SESSIONS]]


def _base_session(
    adapter: str, session_id: str, app: str, mtime: int, path: Path
) -> dict[str, Any]:
    return {
        "id": session_id,
        "app": app,
        "adapter": adapter,
        "project": path.stem,
        "cwd": None,
        "model": None,
        "provider": None,
        "state": "idle",
        "isOpen": False,
        "subagentCount": 0,
        "summary": "",
        "startedAt": mtime,
        "updatedAt": mtime,
        "source": "log",
    }


def _parse_claude(tail: _Tail, path: Path, mtime: int, now_ts: int) -> dict[str, Any] | None:
    meaningful = [
        e for e in [tail.first, *tail.entries]
        if isinstance(e, dict) and e.get("type") in ("user", "assistant", "system", "result")
    ]
    if not meaningful:
        return None

    session_id = ""
    cwd = ""
    project = path.stem
    model = None
    last_text = ""
    last_prompt = ""
    open_tool: str | None = None
    subagent_count = 0
    terminal: str | None = None
    failed = False
    started_at = mtime

    for entry in meaningful:
        etype = entry.get("type")
        cwd = str(entry.get("cwd") or cwd)
        session_id = str(entry.get("sessionId") or entry.get("session_id") or session_id)
        title = entry.get("aiTitle") or entry.get("title")
        if isinstance(title, str) and title.strip():
            project = title.strip()
        ts = _timestamp(entry.get("timestamp"))
        if ts:
            started_at = min(started_at, ts)
        message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
        if etype == "assistant":
            model = message.get("model") or model
            text, tools = _content_text_and_tools(message.get("content"))
            if text:
                last_text = text
            if tools:
                open_tool = tools[-1]
                subagent_count = sum(1 for tool in tools if tool in _SUBAGENT_TOOLS)
            if message.get("stop_reason") == "end_turn":
                open_tool = None
                subagent_count = 0
                terminal = "idle"
        elif etype == "user":
            text, tools = _content_text_and_tools(message.get("content"))
            if any(_is_tool_result(block) for block in message.get("content", []) if isinstance(block, dict)):
                open_tool = None
                subagent_count = 0
            elif text:
                last_prompt = text
                terminal = "running"
        elif etype == "result":
            subtype = str(entry.get("subtype", ""))
            if subtype.startswith("error"):
                failed = True
                terminal = "failed"
            elif subtype == "success_delta" or subtype == "success":
                open_tool = None
                terminal = "completed"
            ts = ts or _timestamp(entry.get("timestamp"))

    if not session_id:
        session_id = path.stem
    if cwd:
        project = Path(cwd).name or project
    age = max(0, now_ts - mtime)
    state = _claude_state(terminal, open_tool, subagent_count > 0, failed, age)
    is_open = _log_is_open(state, age)
    summary = _one_line(last_text) or _tool_summary(open_tool) or _one_line(last_prompt)
    session = _base_session("claude_code", f"claude:{session_id}", "Claude Code", mtime, path)
    session.update({
        "project": project, "cwd": cwd or None, "model": model, "provider": "anthropic",
        "state": state, "isOpen": is_open, "subagentCount": subagent_count,
        "summary": summary or _state_caption(state),
        "startedAt": started_at, "updatedAt": mtime,
    })
    return session


def _claude_state(
    terminal: str | None,
    open_tool: str | None,
    subagent_open: bool,
    failed: bool,
    age: int,
) -> str:
    if failed:
        return "failed"
    if subagent_open:
        if age <= BASH_GRACE_SECONDS:
            return "subagents_running"
        return "waiting" if age <= IDLE_VISIBLE_SECONDS else "idle"
    if open_tool:
        grace = BASH_GRACE_SECONDS if open_tool in _BASH_TOOLS else RUNNING_GRACE_SECONDS
        if age <= grace:
            return "running"
        return "waiting" if age <= IDLE_VISIBLE_SECONDS else "idle"
    if terminal == "running":
        return "running" if age <= RUNNING_GRACE_SECONDS else "idle"
    if terminal == "completed":
        return "completed"
    return "idle"


def _parse_codex_compatible(
    adapter: str, tail: _Tail, root: Path, path: Path, mtime: int, now_ts: int
) -> dict[str, Any] | None:
    entries = [e for e in [tail.first, *tail.entries] if isinstance(e, dict)]
    meta = next((e.get("payload", {}) for e in entries if e.get("type") == "session_meta"), {})
    if not isinstance(meta, dict):
        meta = {}
    if not any(e.get("type") in ("session_meta", "event_msg", "response_item") for e in entries):
        return None

    session_id = str(meta.get("id") or path.stem)
    cwd = str(meta.get("cwd") or "")
    project = Path(cwd).name if cwd else path.stem
    app, provider = _session_identity(adapter, meta)
    model = None
    last_text = ""
    last_prompt = ""
    open_tool: str | None = None
    waiting = False
    subagent_count = 0
    terminal: str | None = None
    failed = False
    started_at = mtime

    for entry in entries:
        ts = _timestamp(entry.get("timestamp"))
        if ts:
            started_at = min(started_at, ts)
        etype = entry.get("type")
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            continue
        if etype == "turn_context":
            model = payload.get("model") or model
            provider = payload.get("modelProviderId") or provider
        elif etype == "event_msg":
            kind = payload.get("type")
            text = str(payload.get("message") or "")
            if kind in ("user_message",):
                if text:
                    last_prompt = text
                terminal = "running"
            elif kind == "agent_message":
                if text:
                    last_text = text
            elif kind == "task_started":
                terminal = "running"
            elif kind in ("subagent_started", "agent_spawned", "collaboration_spawned"):
                subagent_count += 1
                terminal = "subagents_running"
            elif kind in ("subagent_stopped", "agent_exited", "collaboration_completed"):
                subagent_count = max(0, subagent_count - 1)
                terminal = "subagents_running" if subagent_count else "running"
            elif kind == "task_complete":
                terminal = "completed"
                waiting = False
                open_tool = None
                subagent_count = 0
            elif kind in ("exec_command_approval_requested", "apply_patch_approval_requested"):
                waiting = True
                terminal = "waiting"
            elif kind in ("exec_command_begin", "tool_call_begin"):
                open_tool = payload.get("tool") or payload.get("command") or "Bash"
                waiting = False
            elif kind in ("exec_command_end", "tool_call_end"):
                open_tool = None
            elif kind == "turn_aborted":
                terminal = "idle"
            elif kind == "error":
                failed = True
                terminal = "failed"
        elif etype == "response_item":
            if payload.get("type") == "message":
                content = payload.get("content")
                text = _response_item_text(content)
                role = payload.get("role")
                if role == "assistant" and text:
                    last_text = text
                elif role == "user" and text:
                    last_prompt = text
            elif payload.get("type") in ("function_call", "local_shell_call"):
                name = payload.get("name") or (payload.get("arguments") and "shell")
                if name:
                    open_tool = str(name)

    age = max(0, now_ts - mtime)
    if failed:
        state = "failed"
    elif subagent_count:
        if age <= BASH_GRACE_SECONDS:
            state = "subagents_running"
        else:
            state = "waiting" if age <= IDLE_VISIBLE_SECONDS else "idle"
    elif waiting:
        state = "waiting" if age <= IDLE_VISIBLE_SECONDS else "idle"
    elif terminal == "completed":
        state = "completed"
    elif open_tool:
        grace = BASH_GRACE_SECONDS if open_tool in _BASH_TOOLS else RUNNING_GRACE_SECONDS
        if age <= grace:
            state = "running"
        else:
            state = "waiting" if age <= IDLE_VISIBLE_SECONDS else "idle"
    elif terminal == "running" and age <= RUNNING_GRACE_SECONDS:
        state = "running"
    else:
        state = "idle"
    summary = _one_line(last_text) or _tool_summary(open_tool) or _one_line(last_prompt)
    session = _base_session(adapter, f"{adapter}:{session_id}", app, mtime, path)
    is_open = _log_is_open(state, age)
    session.update({
        "project": project, "cwd": cwd or None, "model": model, "provider": provider,
        "state": state, "isOpen": is_open, "subagentCount": subagent_count,
        "summary": summary or _state_caption(state),
        "startedAt": started_at, "updatedAt": mtime,
    })
    return session


def _parse_message_log(
    adapter: str, tail: _Tail, root: Path, path: Path, mtime: int, now_ts: int
) -> dict[str, Any] | None:
    entries = [
        e for e in [tail.first, *tail.entries]
        if isinstance(e, dict) and e.get("type") == "message" and isinstance(e.get("message"), dict)
    ]
    if not entries:
        return None

    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = Path(path.name)
    parts = relative.parts
    project = parts[0] if len(parts) > 1 else path.stem
    session_id = f"{adapter}:{relative.with_suffix('')}"
    app = _APP_LABEL[adapter]
    model = None
    provider = None
    last_text = ""
    last_prompt = ""
    got_answer = False
    subagent_count = 0
    started_at = mtime

    for entry in entries:
        message = entry["message"]
        role = message.get("role")
        ts = _timestamp(message.get("timestamp")) or _timestamp(entry.get("timestamp"))
        if ts:
            started_at = min(started_at, ts)
        model = message.get("model") or model
        provider = message.get("provider") or provider
        text, tools = _content_text_and_tools(message.get("content"))
        subagent_count = sum(1 for tool in tools if tool in _SUBAGENT_TOOLS)
        if role == "assistant":
            if text:
                last_text = text
            got_answer = True
        elif role == "user" and text:
            last_prompt = text
            got_answer = False

    age = max(0, now_ts - mtime)
    if got_answer:
        state = "idle" if age > RUNNING_GRACE_SECONDS else "running"
    else:
        if age <= RUNNING_GRACE_SECONDS:
            state = "running"
        else:
            state = "waiting" if age <= IDLE_VISIBLE_SECONDS else "idle"
    if subagent_count:
        if age <= BASH_GRACE_SECONDS:
            state = "subagents_running"
        elif age <= IDLE_VISIBLE_SECONDS:
            state = "waiting"
        else:
            state = "idle"
    summary = _one_line(last_text) or _one_line(last_prompt)
    session = _base_session(adapter, session_id, app, mtime, path)
    session.update({
        "project": project,
        "model": model, "provider": provider, "state": state,
        "isOpen": _log_is_open(state, age),
        "subagentCount": subagent_count,
        "summary": summary or _state_caption(state),
        "startedAt": started_at, "updatedAt": mtime,
    })
    return session


# --------------------------------------------------------------------------- #
# Hook overlay
# --------------------------------------------------------------------------- #


def _live_hooks(state: dict[str, Any], now_ts: int) -> Iterable[tuple[str, dict[str, Any]]]:
    hooks = state.get("agentSessions")
    if not isinstance(hooks, dict):
        return ()
    live = []
    for session_id, record in hooks.items():
        if not isinstance(record, dict):
            continue
        ttl = HOOK_TTL_SECONDS.get(str(record.get("state")), 0)
        if ttl and now_ts - int(record.get("at", 0)) <= ttl:
            live.append((str(session_id), record))
    return live


def _hook_session(session_id: str, hook: dict[str, Any]) -> dict[str, Any]:
    state_name = str(hook.get("state", "running"))
    display_state = {"started": "running", "completed": "idle"}.get(state_name, state_name)
    app = str(hook.get("app") or hook.get("source") or "Agent")
    cwd = str(hook.get("cwd") or "")
    session_prefix = session_id.split(":", 1)[0] if ":" in session_id else "hook"
    adapter = {"claude": "claude_code"}.get(session_prefix, session_prefix)
    return {
        "id": session_id,
        "app": app.title() if app.islower() else app,
        "adapter": adapter,
        "project": Path(cwd).name if cwd else app,
        "cwd": cwd or None,
        "model": hook.get("model"),
        "provider": None,
        "state": display_state,
        "isOpen": display_state in OPEN_STATES,
        "subagentCount": int(hook.get("subagentCount", 1 if display_state == "subagents_running" else 0) or 0),
        "summary": _state_caption(display_state),
        "startedAt": int(hook.get("at", 0)),
        "updatedAt": int(hook.get("at", 0)),
        "source": "hook",
    }


# --------------------------------------------------------------------------- #
# Content helpers
# --------------------------------------------------------------------------- #


def _content_text_and_tools(content: Any) -> tuple[str, list[str]]:
    """Return (joined visible text, ordered tool-call names) from a message."""
    if isinstance(content, str):
        return _clean_claude_text(content), []
    if not isinstance(content, list):
        return "", []
    texts: list[str] = []
    tools: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            if isinstance(block, str) and _clean_claude_text(block):
                texts.append(_clean_claude_text(block))
            continue
        btype = block.get("type")
        if btype == "text":
            text = _clean_claude_text(str(block.get("text") or ""))
            if text:
                texts.append(text)
        elif btype in ("tool_use", "function_call", "local_shell_call"):
            name = block.get("name") or block.get("tool")
            if name:
                tools.append(str(name))
        elif btype == "toolCall" and isinstance(block.get("tool"), str):
            tools.append(block["tool"])
    return "\n".join(texts).strip(), tools


def _is_tool_result(block: dict[str, Any]) -> bool:
    return block.get("type") in ("tool_result", "toolResult")


def _response_item_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in ("input_text", "output_text", "text"):
                text = str(block.get("text") or "").strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


def _tool_summary(tool: str | None) -> str:
    return f"using {tool}" if tool else ""


def _state_caption(state: str) -> str:
    return {
        "running": "agent is working",
        "subagents_running": "subagents are working",
        "waiting": "waiting for approval",
        "idle": "turn finished",
        "completed": "task completed",
        "failed": "task failed",
    }.get(state, state)


def _log_is_open(state: str, age: int) -> bool:
    """Return whether a log-derived session is still honest to display."""
    if state == "idle":
        return age <= IDLE_VISIBLE_SECONDS
    if state == "waiting":
        return age <= IDLE_VISIBLE_SECONDS
    return state in OPEN_STATES


def _one_line(text: str, limit: int = SUMMARY_LIMIT) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed
