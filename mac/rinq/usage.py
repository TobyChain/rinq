"""Incrementally aggregate local coding-agent token usage.

Only token counters and source metadata are retained. Prompt text, assistant
responses, tool arguments, and tool output are never stored by Rinq.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import HOME, ensure_dirs, load_config

USAGE_DB_PATH = HOME / "usage.sqlite3"
DEFAULT_SCAN_DAYS = 7
_LOCK = threading.Lock()


@dataclass(frozen=True)
class UsageSource:
    """A discovered local log root and its parser type."""

    adapter: str
    root: Path


def discover_sources(extra_sources: list[dict[str, str]] | None = None) -> list[UsageSource]:
    """Return standard, user-independent coding-agent log locations."""
    home = Path.home()
    codex_home = _env_path("CODEX_HOME", home / ".codex")
    trae_home = _env_path("TRAE_HOME", home / ".trae")
    traecli_home = _env_path("TRAECLI_HOME", trae_home / "cli")
    claude_home = _env_path("CLAUDE_CONFIG_DIR", home / ".claude")
    candidates = [
        UsageSource("codex", codex_home / "sessions"),
        UsageSource("traex", traecli_home / "sessions"),
        UsageSource("claude_code", claude_home / "projects"),
    ]
    for extra in extra_sources or []:
        if not isinstance(extra, dict):
            continue
        adapter = extra.get("adapter", "")
        path = extra.get("path", "")
        if adapter in {"codex", "traex", "claude_code"} and path:
            candidates.append(UsageSource(adapter, Path(path).expanduser()))
    seen = set()
    result = []
    for source in candidates:
        resolved = source.root.expanduser()
        key = (source.adapter, str(resolved))
        if resolved.is_dir() and key not in seen:
            seen.add(key)
            result.append(UsageSource(source.adapter, resolved))
    return result


def build_usage_summary(now: datetime | None = None) -> dict[str, Any]:
    """Refresh the incremental index and return today plus rolling 7-day usage."""
    local_now = (now or datetime.now().astimezone()).astimezone()
    cfg = load_config()
    usage_cfg = cfg.get("usage")
    usage_cfg = usage_cfg if isinstance(usage_cfg, dict) else {}
    try:
        lookback_days = max(1, min(31, int(usage_cfg.get("lookbackDays", DEFAULT_SCAN_DAYS))))
    except (TypeError, ValueError):
        lookback_days = DEFAULT_SCAN_DAYS
    extra_sources = usage_cfg.get("extraSources")
    extra_sources = extra_sources if isinstance(extra_sources, list) else []
    first_day = local_now.date() - timedelta(days=lookback_days - 1)
    with _LOCK:
        ensure_dirs()
        with sqlite3.connect(USAGE_DB_PATH) as db:
            _ensure_schema(db)
            sources = discover_sources(extra_sources)
            for source in sources:
                _scan_source(db, source, first_day, local_now.tzinfo)
            db.execute("DELETE FROM usage_events WHERE local_date < ?", (first_day.isoformat(),))
            db.commit()
            native_rows = _event_rows(db, first_day)
        cc_rows = _cc_switch_rows(first_day, local_now.tzinfo, native_rows)
        return _summarize(native_rows + cc_rows, sources, local_now.date(), first_day, lookback_days)


def _env_path(name: str, fallback: Path) -> Path:
    """Resolve a path environment variable while treating an empty value as unset."""
    value = os.environ.get(name)
    return Path(value).expanduser() if value else fallback


def _ensure_schema(db: sqlite3.Connection) -> None:
    """Create the private usage index if needed."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS usage_files (
            path TEXT PRIMARY KEY, adapter TEXT NOT NULL, inode INTEGER NOT NULL,
            offset INTEGER NOT NULL, modified_ns INTEGER NOT NULL,
            app TEXT NOT NULL, provider TEXT, model TEXT
        );
        CREATE TABLE IF NOT EXISTS usage_events (
            path TEXT NOT NULL, byte_offset INTEGER NOT NULL, occurred_at INTEGER NOT NULL,
            local_date TEXT NOT NULL, app TEXT NOT NULL, provider TEXT, model TEXT,
            input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            cached_input_tokens INTEGER NOT NULL, cache_write_input_tokens INTEGER NOT NULL,
            reasoning_output_tokens INTEGER NOT NULL,
            PRIMARY KEY (path, byte_offset)
        );
        CREATE INDEX IF NOT EXISTS idx_usage_events_date ON usage_events(local_date);
        """
    )


def _scan_source(
    db: sqlite3.Connection, source: UsageSource, first_day: date, local_tz: Any
) -> None:
    """Scan new bytes from recent JSONL files under one source root."""
    cutoff = datetime.combine(first_day, time.min, local_tz).timestamp() - 86400
    for path in source.root.rglob("*.jsonl"):
        try:
            stat = path.stat()
        except OSError:
            continue
        cursor = db.execute(
            "SELECT inode,offset,modified_ns,app,provider,model FROM usage_files WHERE path=?",
            (str(path),),
        ).fetchone()
        if cursor is None and stat.st_mtime < cutoff:
            continue
        offset = int(cursor[1]) if cursor else 0
        app = str(cursor[3]) if cursor else _default_app(source.adapter)
        provider = cursor[4] if cursor else None
        model = cursor[5] if cursor else None
        if cursor and (int(cursor[0]) != stat.st_ino or stat.st_size < offset):
            db.execute("DELETE FROM usage_events WHERE path=?", (str(path),))
            offset = 0
        if cursor and stat.st_size == offset and int(cursor[2]) == stat.st_mtime_ns:
            continue
        offset, app, provider, model = _scan_file(
            db, source.adapter, path, offset, app, provider, model, first_day, local_tz
        )
        db.execute(
            """INSERT INTO usage_files(path,adapter,inode,offset,modified_ns,app,provider,model)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET adapter=excluded.adapter,inode=excluded.inode,
               offset=excluded.offset,modified_ns=excluded.modified_ns,app=excluded.app,
               provider=excluded.provider,model=excluded.model""",
            (str(path), source.adapter, stat.st_ino, offset, stat.st_mtime_ns, app, provider, model),
        )


def _scan_file(
    db: sqlite3.Connection, adapter: str, path: Path, offset: int, app: str,
    provider: str | None, model: str | None, first_day: date, local_tz: Any
) -> tuple[int, str, str | None, str | None]:
    """Read one JSONL file from offset and index token events only."""
    with path.open("rb") as stream:
        stream.seek(offset)
        committed_offset = offset
        while True:
            line_offset = stream.tell()
            line = stream.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                # The active agent may still be writing this JSON object. Leave
                # it for the next refresh instead of advancing past partial data.
                break
            committed_offset = stream.tell()
            if b"session_meta" in line[:600]:
                obj = _json(line)
                if obj and obj.get("type") == "session_meta":
                    app, provider = _session_identity(adapter, obj.get("payload", {}))
                    continue
            if b"turn_context" in line[:500]:
                obj = _json(line)
                if obj and obj.get("type") == "turn_context":
                    payload = obj.get("payload", {})
                    model = payload.get("model") or model
                    provider = payload.get("model_provider") or provider
                    continue
            event = _token_event(adapter, line, app, provider, model, local_tz)
            if event is None or date.fromisoformat(event[1]) < first_day:
                continue
            db.execute(
                """INSERT OR IGNORE INTO usage_events(
                    path,byte_offset,occurred_at,local_date,app,provider,model,
                    input_tokens,output_tokens,cached_input_tokens,
                    cache_write_input_tokens,reasoning_output_tokens
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (str(path), line_offset, *event),
            )
        return committed_offset, app, provider, model


def _token_event(
    adapter: str, line: bytes, app: str, provider: str | None,
    current_model: str | None, local_tz: Any
) -> tuple[Any, ...] | None:
    """Parse one top-level token event from Codex/TraeX/Claude Code."""
    obj = None
    usage = None
    model = current_model
    if b"token_count" in line:
        obj = _json(line)
        payload = obj.get("payload", {}) if obj else {}
        if obj and obj.get("type") == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info", {})
            usage = info.get("last_token_usage")
            context = payload.get("context", {})
            model = context.get("model") or model
            provider = context.get("modelProviderId") or provider
    elif adapter == "claude_code" and b"assistant" in line and b"usage" in line:
        obj = _json(line)
        message = obj.get("message", {}) if obj else {}
        if obj and obj.get("type") == "assistant":
            usage = message.get("usage")
            model = message.get("model") or model
    if not obj or not usage:
        return None
    occurred_at = _timestamp(obj.get("timestamp"))
    if occurred_at is None:
        return None
    local_date = datetime.fromtimestamp(occurred_at, local_tz).date().isoformat()
    return (
        occurred_at, local_date, app, provider, model,
        int(usage.get("input_tokens", 0) or 0),
        int(usage.get("output_tokens", 0) or 0),
        int(usage.get("cached_input_tokens", usage.get("cache_read_input_tokens", 0)) or 0),
        int(usage.get("cache_write_input_tokens", usage.get("cache_creation_input_tokens", 0)) or 0),
        int(usage.get("reasoning_output_tokens", 0) or 0),
    )


def _json(line: bytes) -> dict[str, Any] | None:
    """Decode an external JSONL line, returning None for malformed input."""
    try:
        value = json.loads(line)
        return value if isinstance(value, dict) else None
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _timestamp(value: Any) -> int | None:
    """Convert an ISO-8601 or Unix timestamp to epoch seconds."""
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _default_app(adapter: str) -> str:
    """Return the default product label for a log adapter."""
    return {"codex": "Codex CLI", "traex": "TraeX", "claude_code": "Claude Code"}[adapter]


def _session_identity(adapter: str, payload: dict[str, Any]) -> tuple[str, str | None]:
    """Map portable session metadata to a human-facing local client."""
    provider = payload.get("model_provider")
    if adapter == "traex":
        return "TraeX", provider
    if adapter == "claude_code":
        return "Claude Code", provider or "anthropic"
    originator = str(payload.get("originator", "")).lower()
    source = payload.get("source")
    if "desktop" in originator:
        return "Codex Desktop", provider or "openai"
    if source == "vscode":
        return "Codex IDE", provider or "openai"
    return "Codex CLI", provider or "openai"


def _event_rows(db: sqlite3.Connection, first_day: date) -> list[dict[str, Any]]:
    """Load indexed native events inside the rolling window."""
    columns = [
        "occurredAt", "date", "app", "provider", "model",
        "inputTokens", "outputTokens", "cachedInputTokens",
        "cacheWriteInputTokens", "reasoningOutputTokens",
    ]
    rows = db.execute(
        """SELECT occurred_at,local_date,app,provider,model,input_tokens,output_tokens,
                  cached_input_tokens,cache_write_input_tokens,reasoning_output_tokens
           FROM usage_events WHERE local_date >= ?""",
        (first_day.isoformat(),),
    ).fetchall()
    return [dict(zip(columns, row)) for row in rows]


def _cc_switch_rows(
    first_day: date, local_tz: Any, native_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Read unique cc-switch proxy calls, excluding imported/native duplicates."""
    db_path = _env_path("RINQ_CCSWITCH_DB", Path.home() / ".cc-switch" / "cc-switch.db")
    if not db_path.exists():
        return []
    native_apps = {row["app"] for row in native_rows}
    native_types: set[str] = set()
    if any(app.startswith("Codex") or app == "TraeX" for app in native_apps):
        native_types.add("codex")
    if "Claude Code" in native_apps:
        native_types.add("claude")
    cutoff = int(datetime.combine(first_day, time.min, local_tz).timestamp())
    try:
        with sqlite3.connect(db_path) as db:
            rows = db.execute(
                """SELECT created_at,app_type,provider_id,model,input_tokens,output_tokens,
                          cache_read_tokens,cache_creation_tokens,data_source
                   FROM proxy_request_logs WHERE created_at >= ?""",
                (cutoff,),
            ).fetchall()
    except sqlite3.Error:
        return []
    result = []
    labels = {"codex": "Codex (cc-switch)", "claude": "Claude Code (cc-switch)",
              "gemini": "Gemini CLI", "opencode": "OpenCode"}
    for created, app_type, provider, model, inp, out, cache_read, cache_write, data_source in rows:
        if data_source != "proxy" or app_type in native_types:
            continue
        result.append({
            "occurredAt": int(created),
            "date": datetime.fromtimestamp(created, local_tz).date().isoformat(),
            "app": labels.get(app_type, f"cc-switch / {app_type}"),
            "provider": provider, "model": model,
            "inputTokens": int(inp or 0), "outputTokens": int(out or 0),
            "cachedInputTokens": int(cache_read or 0),
            "cacheWriteInputTokens": int(cache_write or 0),
            "reasoningOutputTokens": 0,
        })
    return result


def _summarize(
    rows: list[dict[str, Any]], sources: Iterable[UsageSource], today: date,
    first_day: date, lookback_days: int
) -> dict[str, Any]:
    """Aggregate normalized events into today, last-7-days, daily, and app views."""
    days = [(first_day + timedelta(days=i)).isoformat() for i in range(lookback_days)]
    by_day = {day: _totals() for day in days}
    by_app: dict[str, dict[str, Any]] = {}
    today_totals = _totals()
    week_totals = _totals()
    for row in rows:
        if row["date"] not in by_day:
            continue
        _add(by_day[row["date"]], row)
        _add(week_totals, row)
        app_totals = by_app.setdefault(row["app"], {"app": row["app"], **_totals()})
        _add(app_totals, row)
        if row["date"] == today.isoformat():
            _add(today_totals, row)
    source_status = []
    for source in sources:
        source_status.append({"adapter": source.adapter, "available": True})
    cc_path = _env_path("RINQ_CCSWITCH_DB", Path.home() / ".cc-switch" / "cc-switch.db")
    if cc_path.exists():
        source_status.append({"adapter": "cc_switch", "available": True})
    return {
        "version": 1,
        "updatedAt": int(datetime.now(tz=timezone.utc).timestamp()),
        "today": {"date": today.isoformat(), **today_totals},
        "week": {"startDate": first_day.isoformat(), "endDate": today.isoformat(), **week_totals},
        "daily": [{"date": day, **by_day[day]} for day in days],
        "apps": sorted(by_app.values(), key=lambda item: item["totalTokens"], reverse=True),
        "sources": source_status,
    }


def _totals() -> dict[str, int]:
    """Return an empty token total record."""
    return {"inputTokens": 0, "outputTokens": 0, "cachedInputTokens": 0,
            "cacheWriteInputTokens": 0, "reasoningOutputTokens": 0,
            "totalTokens": 0, "requests": 0}


def _add(total: dict[str, Any], row: dict[str, Any]) -> None:
    """Add one normalized usage event to an aggregate."""
    for key in ("inputTokens", "outputTokens", "cachedInputTokens",
                "cacheWriteInputTokens", "reasoningOutputTokens"):
        total[key] += int(row.get(key, 0) or 0)
    total["totalTokens"] += int(row.get("inputTokens", 0) or 0) + int(row.get("outputTokens", 0) or 0)
    total["requests"] += 1
