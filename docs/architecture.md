# Rinq architecture

Rinq has a macOS daemon and menu-bar client, plus independent iOS/watchOS
clients. Provider quotas and local agent usage remain separate data sources.

```text
Provider HTTPS APIs ── concurrent collectors ── /status ── quota rows + alerts
Local JSONL counters ── incremental SQLite ──── /usage ─── daily usage views
Local transcript tails + lifecycle hooks ───── /sessions ─ open-session panel

iOS / watchOS ── direct provider HTTPS ── shared model ── widgets / complications
```

## Provider quota path

`mac/rinq/collectors.py` selects providers with an API key or supported local
account. Up to eight providers are fetched concurrently. A failed provider
retains an unavailable status row without failing other providers. Logs contain
the endpoint without query parameters or credentials and the exception class.
An explicit `collectors: ["mock"]` keeps the collector in offline demo mode.

On macOS credentials activate a provider automatically. The Providers tab shows
connection state and key entry; it has no lightning indicator or activation
switch. `GET /config` retains `enabled` as a compatibility field equal to
`hasCredential`. Old activation settings do not override credential detection.
Credentials do not prove API support or successful quota lookup.

`usedValue`, `totalValue`, and `valueUnit` are the quota contract.
`usedPercent` is only the normalized rendering value. Each macOS quota row has
its own trailing ring; iOS/watchOS retain their shared native ring views.

## Local agent path

`mac/rinq/usage.py` indexes structured token counts and source metadata in
SQLite. It supports Codex, TraeX, Claude Code, ZCode, OMP, and Pi. Conversation
content is excluded from that index.

`mac/rinq/sessions.py` reads bounded JSONL tails for Claude Code, Codex, TraeX,
OMP, and Pi. It creates a one-line summary in memory, then overlays lifecycle
state from hooks. `/sessions` returns at most twelve sessions ordered by CLI,
app, and running / subagents running / waiting / idling. `SessionEnd` removes
a session. Without lifecycle hooks, visibility is inferred from recent log
activity rather than terminal-process inspection; see `schema/status.md` for
time limits. Hook records contain state and metadata, never prompt or reply text.

The macOS `Store` publishes session snapshots independently of provider quota
responses. While the popover is open, it requests `/sessions` every two seconds;
closing the popover cancels that task. The daemon caches scans for five seconds
and invalidates the snapshot after lifecycle events. General quota, settings,
and usage refresh remains on the thirty-second application timer.

## UI and distribution

The macOS popover is at most 480 points wide and uses up to 62% of the visible
screen height, including its outer frame. Sparse dashboards retain a minimum
content height of 316 points when the screen permits. The session panel has
space for up to five rows, with further sessions available by scrolling.
Alerts reserve their layout slot until the popover closes; dismissing an alert
does not move the quota rows or session panel.

Source installs use `install.sh`. DMG bundles use `DaemonSetup.swift` and the
bundled `install-daemon.sh` for bootstrap. `scripts/build-dmg.sh` and
`scripts/release.sh` provide the v0.1.8 distribution path. Building the menu-bar
executable does not install or restart the user's runtime.

The daemon binds to `127.0.0.1:7788` by default. Configuration and account
connection writes are restricted to loopback clients. The iOS/watchOS clients
fetch providers directly and do not use the Mac session endpoint.
JSON responses use `Cache-Control: no-store` and do not grant cross-origin
browser access, so arbitrary websites cannot read local session summaries.
