# Rinq status contract

One JSON document, served at `GET /status` and consumed by the watch app and
the complication. All timestamps are Unix epoch seconds.

```json
{
  "version": 1,
  "updatedAt": 1757300000,
  "rings": [
    {
      "id": "codex-5h",
      "label": "Codex 5h",
      "vendor": "codex",
      "kind": "window",
      "usedPercent": 68,
      "usedValue": 68,
      "totalValue": 100,
      "valueUnit": "percent",
      "resetsAt": 1757303000,
      "windowMins": 300,
      "accent": "blue"
    },
    {
      "id": "deepseek-balance",
      "label": "DeepSeek",
      "vendor": "deepseek",
      "kind": "balance",
      "usedPercent": 34,
      "usedValue": 3.38,
      "totalValue": 10.0,
      "valueUnit": "CNY",
      "remaining": 6.62,
      "currency": "CNY",
      "accent": "teal"
    },
    {
      "id": "openai-api",
      "label": "OpenAI API",
      "vendor": "openai",
      "kind": "budget",
      "usedPercent": 37,
      "usedValue": 7.42,
      "totalValue": 20.0,
      "valueUnit": "USD",
      "spentUsd": 7.42,
      "budgetUsd": 20.0,
      "resetsAt": 1759737600,
      "windowMins": 43200,
      "accent": "green"
    }
  ],
  "agents": {
    "running": 1, "subagentsRunning": 0, "waiting": 0,
    "doneToday": 2, "failedToday": 0,
    "lastEvent": { "state": "completed", "title": "Agent completed", "at": 1757300000 }
  },
  "focus": { "mode": "focus", "remainingMins": 31, "breakEveryMins": 50 }
}
```

## Ring kinds

All user-facing quota values use `usedValue / totalValue`. `valueUnit` is
`percent`, `requests`, `USD`, `CNY`, or `tokens`; views format it consistently
(`tokens` uses K/M/B shorthand). `usedPercent` remains the normalized 0..100
fill used to draw the ring.

- `window` — a rate-limit window (5h, weekly). `resetsAt` is the next reset.
  `usedPercent` = quota consumed.
- `budget` — postpaid spend against a user-set monthly budget. `spentUsd` /
  `budgetUsd` present; `usedPercent = spent/budget*100`.
- `balance` — prepaid / pay-as-you-go remaining balance (Chinese vendors bill
  in CNY). `remaining` is the amount left in `currency`. `usedPercent` is the
  consumed share of a user-set reference top-up (`balanceFull` in config, same
  currency); it is `null` when no reference is configured, in which case the
  watch shows the absolute remaining amount and a grey ring.

## Rules

- `rings[].usedPercent` is 0..100, already clamped by the collector. Use `null`
  with `"status": "unknown"` when the value cannot be obtained; never send a
  stale number without `updatedAt` reflecting it.
- `status` on a `status`-kind ring is one of `not_connected` (no credential),
  `quota_unavailable` (credential present but the live call failed), or
  `quota_unsupported` (provider has no implemented live-quota route). These
  render as grey, non-alerting cards.
- `accent` is one of: `blue indigo green orange red purple teal`. Unknown
  values fall back to `blue` on the watch.
- Events (`POST /event`) use states: `started running subagents_running waiting
  idle completed failed closed`.
  Optional fields are `source`, `app`, `title`, `detail`, `sessionId`, `cwd`,
  and `model`. When `sessionId` is present the event also updates the
  `GET /sessions` overlay (`agentSessions` in daemon state) keyed by that id;
  `SessionEnd` uses `closed` and clears the session from the open-session list.
  Overlay records expire per state (5m for started/running/subagents_running,
  10m for waiting/idle, 1h for completed/failed). Only lifecycle state, app,
  cwd, model, subagent count and timestamps are persisted. Event title/detail
  never enter persisted session records; summaries come from transcript tails
  in memory. A completed hook marks the end of a turn and displays as idle.
- `agents.running`, `agents.subagentsRunning`, and `agents.waiting` in
  `GET /status` are overwritten with the live counts from `GET /sessions` on
  every build. `doneToday` and `failedToday` remain hook-derived daily
  counters.

## Local agent sessions

`GET /sessions` returns a quick-glance snapshot of open local terminal-agent
sessions, rebuilt in memory from JSONL transcripts on every request (scans are
throttled to one per 5 seconds). Closed sessions are omitted. Without hooks,
idle or waiting activity remains visible for at most 10 minutes; open shell
commands and subagent activity retain a 15-minute running grace window.
Prompt and assistant text is never persisted; only a one-line summary is
returned. All timestamps are Unix epoch seconds.
JSON responses disable HTTP caching and do not allow cross-origin browser reads.

```json
{
  "version": 1,
  "updatedAt": 1757300000,
  "counts": {
    "running": 1, "subagentsRunning": 1, "waiting": 1, "idle": 1,
    "active": 3, "open": 4,
    "doneToday": 3, "failedToday": 0
  },
  "sessions": [
    {
      "id": "claude:7f3a…",
      "app": "Claude Code",
      "adapter": "claude_code",
      "project": "rinq",
      "cwd": "/Users/me/code/rinq",
      "model": "claude-sonnet-4-5",
      "provider": "anthropic",
      "state": "waiting",
      "isOpen": true,
      "subagentCount": 0,
      "summary": "using Bash",
      "startedAt": 1757299000,
      "updatedAt": 1757300000,
      "source": "log"
    }
  ]
}
```

- `state` for displayed open sessions is one of `running`,
  `subagents_running`, `waiting` (approval prompt open), or `idle`. Closed,
  completed, and failed sessions are omitted from the display. Log-derived
  state uses grace windows: a transcript modified within 120s is running; an
  open tool call stays running for 15 minutes (shell tools) or 120 seconds
  (other tools). Stale activity becomes idle and is omitted after its grace
  window; waiting inferred within the 10-minute visibility window is an
  estimate, not proof that an approval dialog is open. Only the 40 newest
  candidate transcripts touched within 24 hours are parsed, using their last
  96KB and up to 80 trailing entries. At most 12 open sessions are returned,
  grouped by CLI (`adapter`) and then
  ordered by running, subagents running, waiting, idling.
- `adapter` is one of `claude_code`, `codex`, `traex`, `omp`, `pi`.
- `isOpen` identifies a session reported open by a fresh hook or inferred open
  from recent log activity. It is not a terminal-process liveness check. `source`
  is `log` (reconstructed from transcript tails) or `hook`
  (authoritative overlay from a `POST /event` carrying the same `sessionId`).
  Hook state overrides log-derived state for the same id while fresh, retaining
  the log-derived summary. A closed-session tombstone suppresses later log
  flushes and late idle/waiting events. A new `started` event explicitly reopens
  that id. Hook updates invalidate the cached snapshot before acknowledgement.
  The macOS popover and web panel poll sessions independently every two seconds.
- Default log roots are `~/.claude/projects`, `~/.codex/sessions`,
  `~/.trae/cli/sessions`, `~/.omp/agent/sessions`, and `~/.pi/agent/sessions`;
  the same client env overrides as `/usage` apply.

## Local IDE integrations

`GET /config` includes an `integrations` array. It reports local installation,
configuration presence, running state, non-secret account status, subscription
entitlement state, and whether structured local usage logs were found.

`authState` and `planState` are populated only for integrations whose local
metadata Rinq parses; every other integration reports `unknown` because Rinq
reads no account data for it. Consumers should treat `unknown` as "not
reported" and omit it rather than presenting it as a problem state.

Each entry carries `monitored`. `POST /config` accepts
`{"monitored": {"<integration id>": false}}` to cancel monitoring and
`true` to resume; cancellations are stored as the `integrationOff` list in
`config.json`. A cancelled IDE is not probed at all, so Rinq reads none of its
files, and its entry keeps only identity fields plus `monitored: false`. It
stays in the array so the row can offer a resume action. Re-reading `/config`
rescans the machine, which is what the Providers tab's IDE refresh button
triggers.

`planState=available` means that the client reports an active subscription or
entitlement. `quotaState=available` is stricter: Rinq must have parsed a
verified `usedValue`/`totalValue` or remaining balance before creating a ring.
Rinq never treats a plan grant limit as current consumption.

Current integration capability levels:

| Integration | Installation / usage | Account state | Verified subscription ring |
|---|---|---|---|
| ZCode | local app + `~/.zcode/cli/log` | ZCode OAuth/provider metadata | plan detected; live balance requires a compatible client response |
| MiMo Code/Desktop | app discovery when installed | official MiMo authorization page | no verified personal balance adapter yet |
| Trae CN | app discovery; TraeX usage is separate | official account page | no verified personal quota endpoint |
| Codex / ChatGPT | existing Codex session logs | local Codex login | supported by existing Codex collector |
| Claude Code | `~/.claude/projects` | local/API configuration | organization API only; consumer plan not exposed |

GitHub Copilot, Cursor, Windsurf, Gemini Code Assist, Zed, Cline, Roo Code,
and Kilo Code may expose plan documentation or local usage, but Rinq must not
infer live remaining quota from plan pricing, UI text, browser cookies, or an
undocumented endpoint.

`POST /auth/connect` accepts `{"integrationId": "zcode"}` from localhost and
opens the vendor's official page in the default browser. It is a convenience
link, not an authentication step: Rinq cannot sign a local CLI or IDE in, so the
macOS UI labels the action "Open vendor page" rather than implying a connection.
The endpoint accepts no passwords or tokens, and Rinq does not read browser
cookies or encrypted credential values.

## Vendors and credentials

On macOS, a discovered credential activates its provider automatically. A key
also adds its provider to a legacy collector list. An explicit
`collectors: ["mock"]` remains an offline demo. Connected providers whose quota
lookup fails retain a grey unavailable row. Credentials establish connection
configuration, not proof that a key is valid or that a quota API is supported.

Quota tracking can be cancelled per vendor without deleting the credential.
`POST /config` accepts `{"tracking": {"<vendor>": false}}` to cancel and
`{"tracking": {"<vendor>": true}}` to resume. Cancellations are stored as the
`trackingOff` list in `config.json`. A cancelled vendor is not fetched and
produces no rings, even while its credential is still detected; saving a new key
for it clears the cancellation. In `GET /config`, the vendor field `tracking` is
the resulting state, so `hasCredential: true` with `tracking: false` means
tracking was cancelled. The retired `enabled` map and response field are gone;
older stored `enabled` values are inert.

| collector | env var | endpoint (base) | kind | verified |
| --- | --- | --- | --- | --- |
| `openai` | `OPENAI_ADMIN_KEY` | `/v1/organization/costs` | budget | route+shape |
| `deepseek` | `DEEPSEEK_API_KEY` | `api.deepseek.com/user/balance` | balance | route (401), shape per docs |
| `moonshot` (Kimi) | `MOONSHOT_API_KEY` | `api.moonshot.cn/v1/users/me/balance` | balance | route (401), shape best-effort |
| `zhipu` (GLM) | `ZHIPU_API_KEY` | `open.bigmodel.cn/api/monitor/usage/quota/limit` | window (fallback balance) | live limits[] windows |
| `minimax` | `MINIMAX_API_KEY` | `api.minimaxi.com/v1/api/openplatform/coding_plan/remains` | window | live 5h/week |
| `xiaomi` (MiMo) | `XIAOMI_API_KEY` | no confirmed public route | balance | stub → not supported |
| `anthropic` (Claude) | `ANTHROPIC_ADMIN_KEY` | Admin Usage & Cost API (org only) | budget | stub → not supported |
| `jina` | `JINA_API_KEY` | `embeddings-dashboard-api.jinaai.cn/api/v1/api_key/user` | balance (tokens) | route confirmed, shape `.wallet.total_balance` |

"route (401)" means the endpoint exists and is auth-gated (probed without a
real key); field parsing follows each vendor's published docs and degrades to
`unknown` if the response shape differs. `codex` 5h/week comes from the local
Codex ChatGPT login and the `chatgpt.com/backend-api/wham/usage` endpoint.

`zhipu` returns rolling `CREDIT_LIMIT` windows (`limits[]` with `usage`,
`remaining`, `nextResetTime`) for coding-plan keys; these render as window rings
(5h/week) and fall back to a prepaid CNY balance when a `balance` field is
present instead. `jina` reads the shared Embeddings/Reranker/Reader/Search token
pool; the key is passed as an `api_key` query parameter and remaining tokens
come from `.wallet.total_balance`. Its host is overridable via `hosts.jina` or
`JINA_DASHBOARD_HOST` (default `embeddings-dashboard-api.jinaai.cn`; use
`embeddings-dashboard-api.jina.ai` for the international host). `anthropic` and
`xiaomi` have no implemented live-quota route and surface an explicit
`quota_unsupported` status when a key is present.

GET /usage returns token counters from local native coding-agent logs. Rinq
reads only structured usage metadata; it does not retain prompt text, assistant
responses, tool arguments, or tool output. Browser and web-app sessions are not
included.

The response contains today, a rolling week, one daily record per day, an apps
breakdown, and discovered sources. The counters are inputTokens,
outputTokens, cachedInputTokens, cacheWriteInputTokens, reasoningOutputTokens,
totalTokens, and requests.

The default sources are ~/.codex/sessions, ~/.trae/cli/sessions,
~/.claude/projects, ~/.zcode/cli/log, ~/.omp/agent/sessions, and
~/.pi/agent/sessions. Set CODEX_HOME, TRAE_HOME/TRAECLI_HOME,
CLAUDE_CONFIG_DIR, ZCODE_HOME, PI_CODING_AGENT_DIR (OMP), or PI_AGENT_DIR (Pi)
when a client stores logs elsewhere. Rinq
reads only structured token counters from ZCode logs and uses an incremental
index under ~/.rinq/usage.sqlite3; it does not retain prompts, responses, tool
arguments, or credential values.
Optional usage.extraSources entries can add another supported local log root
with an adapter and path.
