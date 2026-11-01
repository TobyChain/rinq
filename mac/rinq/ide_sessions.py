"""IDE chat-session discovery for the VSCode product family.

Rinq derives live chat sessions from the per-workspace stores that
VSCode-family editors keep under ``User/workspaceStorage``. The reader is
capability-detected: a workspace is parsed only when its ``state.vscdb``
carries the ``chat.ChatSessionStore.index`` key and matching
``chatSessions/<id>.json`` files exist, so editors with different storage
layouts are skipped instead of being misread.

Only state and one-line summaries are produced, rebuilt in memory on every
scan and never persisted. A workspace whose product was cancelled in the
Integrations settings is not read at all.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
from pathlib import Path
from typing import Any

# Products whose chat transcripts follow the VSCode chat-session store shape.
# ``id`` matches the integration ids where an entry exists so that cancelling
# an IDE in settings also stops reading its chats.
IDE_PRODUCTS: tuple[dict[str, str], ...] = (
    {
        "id": "vscode",
        "label": "VSCode",
        "app": "Visual Studio Code",
        "user_dir": "Library/Application Support/Code/User",
    },
    {
        "id": "vscode-insiders",
        "label": "VSCode Insiders",
        "app": "Visual Studio Code - Insiders",
        "user_dir": "Library/Application Support/Code - Insiders/User",
    },
    {
        "id": "vscodium",
        "label": "VSCodium",
        "app": "VSCodium",
        "user_dir": "Library/Application Support/VSCodium/User",
    },
    {
        "id": "trae",
        # The Integrations definition for Trae uses this id; cancellations in
        # settings record it, so chat reads must honor it too.
        "integration_id": "trae-cn",
        "label": "Trae",
        "app": "Trae",
        "user_dir": "Library/Application Support/Trae/User",
    },
    {
        "id": "cursor",
        "label": "Cursor",
        "app": "Cursor",
        "user_dir": "Library/Application Support/Cursor/User",
    },
    {
        "id": "windsurf",
        "label": "Windsurf",
        "app": "Windsurf",
        "user_dir": "Library/Application Support/Windsurf/User",
    },
)

ADAPTER = "vscode_chat"
# Workspaces untouched for a week are not scanned; keeps the sqlite work bounded.
WORKSPACE_RECENT_SECONDS = 7 * 24 * 3600
MAX_WORKSPACES = 24
MAX_IDE_SESSIONS = 12
# Chat files above this size are summarized from index metadata only.
MAX_CHAT_FILE_BYTES = 3 * 1024 * 1024
INDEX_KEY = "chat.ChatSessionStore.index"
CHAT_INDEX_SQL = "SELECT value FROM ItemTable WHERE key = ?"


def collect_ide_sessions(
    now_ts: int | None = None,
    disabled_ids: set[str] | frozenset[str] | None = None,
    exclude_ids: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    """Return IDE chat sessions across all detectable VSCode-family editors."""
    now_ts = now_ts if now_ts is not None else int(time.time())
    disabled = disabled_ids or set()
    excluded = exclude_ids or set()
    home = _ide_home()
    sessions: list[dict[str, Any]] = []
    for product in IDE_PRODUCTS:
        if product.get("integration_id", product["id"]) in disabled:
            continue
        user_dir = home / product["user_dir"]
        workspaces = user_dir / "workspaceStorage"
        if not workspaces.is_dir():
            continue
        for ws_dir in _recent_workspaces(workspaces, now_ts):
            sessions.extend(_workspace_sessions(product, ws_dir, now_ts))
    # Filter closed sessions before truncating so closing many chats cannot
    # push live ones out of the panel.
    sessions = [s for s in sessions if s["id"] not in excluded]
    sessions.sort(key=lambda s: -int(s.get("updatedAt", 0)))
    return sessions[:MAX_IDE_SESSIONS]


def _ide_home() -> Path:
    override = None
    try:
        import os

        override = os.environ.get("RINQ_IDE_HOME")
    except Exception:
        override = None
    return Path(override).expanduser() if override else Path.home()


def _recent_workspaces(workspaces: Path, now_ts: int) -> list[Path]:
    cutoff = now_ts - WORKSPACE_RECENT_SECONDS
    candidates: list[tuple[int, Path]] = []
    try:
        entries = list(workspaces.iterdir())
    except OSError:
        return []
    for entry in entries:
        if not entry.is_dir():
            continue
        try:
            mtime = int(entry.stat().st_mtime)
        except OSError:
            continue
        if mtime >= cutoff:
            candidates.append((mtime, entry))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in candidates[:MAX_WORKSPACES]]


def _workspace_sessions(
    product: dict[str, str], ws_dir: Path, now_ts: int
) -> list[dict[str, Any]]:
    index = _read_chat_index(ws_dir / "state.vscdb")
    if index is None:
        return []
    folder, folder_path = _read_workspace_folder(ws_dir / "workspace.json")
    entries = index.get("entries") if isinstance(index, dict) else None
    if not isinstance(entries, dict):
        return []
    chat_dir = ws_dir / "chatSessions"
    sessions: list[dict[str, Any]] = []
    for session_id, meta in entries.items():
        if not isinstance(session_id, str) or not isinstance(meta, dict):
            continue
        if meta.get("isEmpty") is True:
            continue
        updated_sec = _epoch_ms(meta.get("lastMessageDate"))
        if updated_sec and now_ts - updated_sec > 24 * 3600:
            continue
        detail = _read_chat_file(chat_dir / f"{session_id}.json")
        session = _ide_session(
            product, session_id, meta, detail, folder, folder_path, now_ts
        )
        if session is not None:
            sessions.append(session)
    return sessions


def _read_chat_index(db_path: Path) -> dict[str, Any] | None:
    """Read the chat session index; None means this editor does not use it."""
    if not db_path.is_file():
        return None
    try:
        uri = db_path.as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=0.5)
        try:
            row = conn.execute(CHAT_INDEX_SQL, (INDEX_KEY,)).fetchone()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return None
    if not row or not row[0]:
        return None
    try:
        parsed = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_workspace_folder(path: Path) -> tuple[str, str | None]:
    """Return (project name, folder path or None) for one workspace."""
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return "workspace", None
    uri = str(payload.get("folder") or "")
    if not uri:
        return "workspace", None
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme in ("", "file"):
        folder_path = urllib.parse.unquote(parsed.path) or None
        name = Path(folder_path).name if folder_path else None
        return (name or "workspace"), folder_path
    # Remote/untitled workspaces cannot be opened locally; keep a display name.
    tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return (tail or parsed.scheme), None


def _read_chat_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.stat().st_size > MAX_CHAT_FILE_BYTES:
            return None
        parsed = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _ide_session(
    product: dict[str, str],
    session_id: str,
    meta: dict[str, Any],
    detail: dict[str, Any] | None,
    folder: str,
    folder_path: str | None,
    now_ts: int,
) -> dict[str, Any] | None:
    updated_sec = _epoch_ms(
        (detail or {}).get("lastMessageDate") or meta.get("lastMessageDate")
    )
    updated_at = updated_sec or int(now_ts)
    requests = (detail or {}).get("requests")
    last_request = requests[-1] if isinstance(requests, list) and requests else None
    user_text = _request_user_text(last_request)
    assistant_text = _request_assistant_text(last_request)
    model = str(last_request.get("modelId") or "") if isinstance(last_request, dict) else ""

    answered = bool(
        isinstance(last_request, dict)
        and (last_request.get("responseId") or last_request.get("response"))
    )
    age = max(0, now_ts - updated_at)
    if not answered:
        state = "running" if age <= 120 else "waiting"
    else:
        state = "running" if age <= 120 else "idle"
    if age > 10 * 60:
        is_open = False
    else:
        is_open = state in ("running", "waiting", "idle")

    summary = assistant_text or user_text or str(meta.get("title") or "")
    return {
        "id": f"{product['id']}:{session_id}",
        "app": product["label"],
        "adapter": ADAPTER,
        "project": folder,
        "cwd": folder_path,
        "model": model or None,
        "provider": None,
        "state": state,
        "isOpen": is_open,
        "subagentCount": 0,
        "summary": _one_line(summary),
        "startedAt": _epoch_ms((detail or {}).get("creationDate")) or updated_at,
        "updatedAt": updated_at,
        "source": "log",
    }


def _request_user_text(request: Any) -> str:
    if not isinstance(request, dict):
        return ""
    message = request.get("message")
    if isinstance(message, dict):
        return str(message.get("text") or "")
    return ""


def _request_assistant_text(request: Any) -> str:
    if not isinstance(request, dict):
        return ""
    response = request.get("response")
    if not isinstance(response, list):
        return ""
    parts: list[str] = []
    for block in response:
        if not isinstance(block, dict) or block.get("kind") != "markdownContent":
            continue
        content = block.get("content")
        if isinstance(content, dict) and content.get("value"):
            parts.append(str(content["value"]))
        elif isinstance(content, str) and content:
            parts.append(content)
        elif isinstance(content, list):
            for piece in content:
                if isinstance(piece, dict) and piece.get("value"):
                    parts.append(str(piece["value"]))
    return "\n".join(parts).strip()


def _epoch_ms(value: Any) -> int:
    try:
        return int(value) // 1000 if value else 0
    except (TypeError, ValueError):
        return 0


def _one_line(text: str, limit: int = 160) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed
