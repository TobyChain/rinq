"""SSH remote agent-session monitoring.

Rinq can watch agent CLI sessions that run on machines Rinq reaches over SSH.
A read-only probe script is piped to ``python3 -`` on the remote host; it
reports the recent transcript tails in the same shapes the local scanner
already parses. Only state and one-line summaries are derived, in memory,
never persisted. Connections use BatchMode (no interactive prompts) and an
SSH ControlMaster socket under ``~/.rinq/ssh/`` so periodic scans reuse one
connection per host instead of opening new ones.

A background refresher scans serially, one host at a time, and keeps the last
good snapshot while a host is unreachable, so a dropped VPN does not flash the
panel empty. Without the refresher (``rinq sessions`` CLI), the scan runs
inline once.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Callable

SCAN_INTERVAL_SECONDS = 45
CONNECT_TIMEOUT_SECONDS = 8
PROBE_TIMEOUT_SECONDS = 20
TAIL_BYTES = 96 * 1024
MAX_TAIL_ENTRIES = 80
MAX_FILES_PER_ROOT = 40
RECENT_SECONDS = 24 * 3600
CONTROL_PATH_DIR = Path.home() / ".rinq" / "ssh"

# Same adapters the local session scanner understands; the probe reports
# these roots and the local parsers stay authoritative.
PROBE_ROOTS: tuple[tuple[str, str], ...] = (
    ("claude_code", "~/.claude/projects"),
    ("codex", "~/.codex/sessions"),
    ("traex", "~/.trae/cli/sessions"),
    ("omp", "~/.omp/agent/sessions"),
    ("pi", "~/.pi/agent/sessions"),
)

# Runs on the remote host; prints one JSON array of transcript tails.
# Deliberately stdlib-only and tolerant: unreadable files are skipped. The
# file's true first line ships alongside the tail window so the local codex
# parser can still find its session_meta record.
PROBE_SCRIPT = """
import glob, json, os, time
ROOTS = %(roots)s
CUTOFF = time.time() - %(recent)d
out = []
for adapter, root in ROOTS:
    base = os.path.expanduser(root)
    found = []
    for path in glob.iglob(os.path.join(base, "**", "*.jsonl"), recursive=True):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if mtime >= CUTOFF:
            found.append((mtime, path))
    found.sort(reverse=True)
    for mtime, path in found[:%(max_files)d]:
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as stream:
                first = stream.readline().decode("utf-8", "replace").strip()
                stream.seek(max(0, size - %(tail)d))
                raw = stream.read().decode("utf-8", "replace")
        except OSError:
            continue
        lines = raw.splitlines()
        if size > %(tail)d and lines:
            lines = lines[1:]
        out.append({"adapter": adapter, "root": base, "path": path,
                    "mtime": int(mtime), "first": first or None,
                    "lines": lines[-%(tail_entries)d:]})
print(json.dumps(out))
""" % {
    "roots": json.dumps([[a, r] for a, r in PROBE_ROOTS]),
    "recent": RECENT_SECONDS,
    "max_files": MAX_FILES_PER_ROOT,
    "tail": TAIL_BYTES,
    "tail_entries": MAX_TAIL_ENTRIES,
}


def normalize_remotes(raw: Any) -> list[dict[str, str]]:
    """Accept ``["host", {"id": ..., "destination": ...}]`` config shapes."""
    remotes: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return remotes
    for entry in raw:
        if isinstance(entry, str) and entry.strip():
            remotes.append({"id": entry.strip(), "destination": entry.strip()})
        elif isinstance(entry, dict):
            destination = str(entry.get("destination") or "").strip()
            if destination:
                remotes.append({
                    "id": str(entry.get("id") or "").strip() or destination,
                    "destination": destination,
                })
    return remotes


def collect_remote_sessions(
    remotes: list[dict[str, str]],
    now_ts: int | None = None,
    runner: Callable[[str], str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Scan each remote serially; return (sessions, per-host status).

    Hosts that share one filesystem (an NFS home, for example) report the
    same transcript through different host ids, so sessions are deduplicated
    across hosts by their underlying transcript identity. The copy from the
    host with the freshest activity wins and carries that host's id, because
    that host is where the agent process actually lives. An unreachable host
    contributes nothing here; the refresher keeps its previous sessions
    visible while it stays down.
    """
    now_ts = now_ts if now_ts is not None else int(time.time())
    runner = runner or _run_probe
    collected: list[dict[str, Any]] = []
    status: list[dict[str, str]] = []
    for remote in remotes:
        remote_id = remote["id"]
        try:
            output = runner(remote["destination"])
            parsed = _sessions_from_probe(_parse_probe_output(output), remote_id, now_ts)
            collected.extend(parsed)
            status.append({"id": remote_id, "state": "ok"})
        except (
            subprocess.SubprocessError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ):
            status.append({"id": remote_id, "state": "unreachable"})
    return _merge_and_dedupe(collected), status


def _parse_probe_output(output: str) -> Any:
    """Parse the probe payload, tolerating shell-banner noise before it."""
    text = output.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        idx = text.find("[")
        if idx < 0:
            raise
        return json.loads(text[idx:])


def _merge_and_dedupe(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate sessions that share one underlying transcript identity."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for session in sessions:
        remote = str(session.get("remote") or "")
        prefix_len = len(remote) + 1 if remote else 0
        key = (str(session.get("adapter")), session["id"][prefix_len:])
        current = best.get(key)
        if current is None or int(session.get("updatedAt", 0)) > int(current.get("updatedAt", 0)):
            best[key] = session
    return list(best.values())


def _run_probe(destination: str) -> str:
    CONTROL_PATH_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={CONNECT_TIMEOUT_SECONDS}",
        "-o", "ControlMaster=auto",
        "-o", f"ControlPath={CONTROL_PATH_DIR}/cm-%C",
        "-o", "ControlPersist=900",
        destination,
        "python3 -",
    ]
    result = subprocess.run(
        command,
        input=PROBE_SCRIPT,
        capture_output=True,
        text=True,
        timeout=PROBE_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"probe exited {result.returncode}")
    return result.stdout


def _sessions_from_probe(
    probe: Any, remote_id: str, now_ts: int
) -> list[dict[str, Any]]:
    """Parse probe output with the local transcript parsers."""
    # Imported here: sessions.py imports this module at the top level and the
    # shared parsers would otherwise form a circular import.
    from .sessions import (
        _json,
        _parse_claude,
        _parse_codex_compatible,
        _parse_message_log,
        _Tail,
    )

    if not isinstance(probe, list):
        return []
    sessions: list[dict[str, Any]] = []
    for item in probe:
        if not isinstance(item, dict):
            continue
        adapter = str(item.get("adapter") or "")
        path_str = str(item.get("path") or "")
        root_str = str(item.get("root") or "")
        mtime = int(item.get("mtime") or 0)
        lines = item.get("lines")
        if adapter not in ("claude_code", "codex", "traex", "omp", "pi"):
            continue
        if not path_str or not root_str or not mtime:
            continue
        if not isinstance(lines, list):
            continue
        entries = [obj for obj in (_json(line) for line in lines) if obj is not None]
        # Prefer the file's true first line (probe-reported) so codex finds
        # its session_meta; fall back to the tail window's first line.
        first_raw = item.get("first")
        first_obj = _json(first_raw) if isinstance(first_raw, str) and first_raw else None
        if first_obj is None and lines:
            first_obj = _json(lines[0])
        tail = _Tail(first=first_obj if isinstance(first_obj, dict) else None, entries=entries)
        root, path = Path(root_str), Path(path_str)
        if adapter == "claude_code":
            session = _parse_claude(tail, path, mtime, now_ts)
        elif adapter in ("codex", "traex"):
            session = _parse_codex_compatible(adapter, tail, root, path, mtime, now_ts)
        else:
            session = _parse_message_log(adapter, tail, root, path, mtime, now_ts)
        if session is None:
            continue
        session["id"] = f"{remote_id}:{session['id']}"
        session["remote"] = remote_id
        sessions.append(session)
    return sessions


# --------------------------------------------------------------------------- #
# Background refresher + stale-while-revalidate snapshot
# --------------------------------------------------------------------------- #


class RemoteSessionRefresher:
    """Serially rescan configured hosts on one background daemon thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: list[dict[str, Any]] = []
        self._status: list[dict[str, str]] = []
        self._updatedAt: int = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="rinq-remote-sessions", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(0):  # first scan immediately
            try:
                self._refresh_once()
            except Exception:
                # Keep the previous snapshot; the next cycle retries. The
                # per-host errors are already folded into the status report,
                # so this only guards truly unexpected failures.
                traceback.print_exc()
            if self._stop.wait(SCAN_INTERVAL_SECONDS):
                return

    def _refresh_once(self) -> None:
        from .config import load_config

        remotes = normalize_remotes(load_config().get("sessionRemotes"))
        if not remotes:
            with self._lock:
                self._sessions = []
                self._status = []
            return
        sessions, status = collect_remote_sessions(remotes)
        unreachable = {st["id"] for st in status if st["state"] == "unreachable"}
        if unreachable:
            # An unreachable host keeps its last good sessions visible until
            # its next successful scan; the panel must not flash empty when
            # the VPN drops.
            with self._lock:
                prev_by_host: dict[str, list[dict[str, Any]]] = {}
                for session in self._sessions:
                    prev_by_host.setdefault(str(session.get("remote") or ""), []).append(session)
            carried: list[dict[str, Any]] = []
            for host in unreachable:
                carried.extend(prev_by_host.get(host, []))
            sessions = _merge_and_dedupe(list(sessions) + carried)
        with self._lock:
            self._sessions = sessions
            self._status = status
            self._updatedAt = int(time.time())

    def snapshot(self) -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
        """(sessions, per-host status, updatedAt); scans inline until started."""
        if self._thread is None:
            self._refresh_once()
        with self._lock:
            return list(self._sessions), list(self._status), self._updatedAt


_refresher = RemoteSessionRefresher()


def start_refresher() -> None:
    _refresher.start()


def remote_snapshot() -> tuple[list[dict[str, Any]], list[dict[str, str]], int]:
    return _refresher.snapshot()
