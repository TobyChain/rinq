"""Read provider credentials from local tool config (cc-switch, Codex auth).

Credentials never leave the machine; they are used only to call each vendor's
quota endpoint over HTTPS. Nothing here is logged.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


def _cc_db_path() -> Path:
    return Path(os.environ.get("RINQ_CCSWITCH_DB", str(Path.home() / ".cc-switch" / "cc-switch.db")))


def ccswitch_provider_key(*, app_type: str, name: str) -> str | None:
    db = _cc_db_path()
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(str(db))
        row = con.execute(
            "SELECT settings_config FROM providers WHERE app_type=? AND name=?",
            (app_type, name),
        ).fetchone()
        con.close()
    except (sqlite3.Error, OSError):
        return None
    if not row:
        return None
    try:
        cfg = json.loads(row[0])
        return cfg.get("auth", {}).get("OPENAI_API_KEY") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def codex_chatgpt_token() -> tuple[str | None, str | None]:
    """Return (access_token, account_id) for the ChatGPT-backed Codex login."""
    path = Path(os.environ.get("RINQ_CODEX_AUTH", str(Path.home() / ".codex" / "auth.json")))
    if not path.exists():
        return None, None
    try:
        auth = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, None
    if auth.get("auth_mode") != "chatgpt":
        return None, None
    tokens = auth.get("tokens", {})
    return tokens.get("access_token"), tokens.get("account_id")
