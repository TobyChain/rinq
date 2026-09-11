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
    "running": 1, "waiting": 0, "doneToday": 2, "failedToday": 0,
    "lastEvent": { "state": "completed", "title": "build passed", "at": 1757300000 }
  },
  "focus": { "mode": "focus", "remainingMins": 31, "breakEveryMins": 50 }
}
```

## Ring kinds

All user-facing quota values use `usedValue / totalValue`. `valueUnit` is
`percent`, `requests`, `USD`, or `CNY`; views format it consistently.
`usedPercent` remains the normalized 0..100 fill used to draw the ring.

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
- `accent` is one of: `blue indigo green orange red purple teal`. Unknown
  values fall back to `blue` on the watch.
- Events (`POST /event`) use states: `started completed failed waiting`.

## Local IDE integrations

`GET /config` includes an `integrations` array. It reports local installation,
configuration presence, running state, non-secret account status, subscription
entitlement state, and whether structured local usage logs were found.

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
opens the vendor's official connection page. It does not accept passwords or
tokens. Rinq does not read browser cookies or encrypted credential values.

## Vendors and credentials

| collector | env var | endpoint (base) | kind | verified |
| --- | --- | --- | --- | --- |
| `openai` | `OPENAI_ADMIN_KEY` | `/v1/organization/costs` | budget | route+shape |
| `deepseek` | `DEEPSEEK_API_KEY` | `api.deepseek.com/user/balance` | balance | route (401), shape per docs |
| `moonshot` (Kimi) | `MOONSHOT_API_KEY` | `api.moonshot.cn/v1/users/me/balance` | balance | route (401), shape best-effort |
| `zhipu` (GLM) | `ZHIPU_API_KEY` | `open.bigmodel.cn/api/monitor/usage/quota/limit` | balance | route (401), shape best-effort |
| `minimax` | `MINIMAX_API_KEY` | `api.minimaxi.com/v1/api/openplatform/coding_plan/remains` | window | live 5h/week |
| `xiaomi` (MiMo) | `XIAOMI_API_KEY` | no confirmed public route | balance | stub → unknown |
| `anthropic` (Claude) | `ANTHROPIC_ADMIN_KEY` | Admin Usage & Cost API (org only) | budget | interface only |

"route (401)" means the endpoint exists and is auth-gated (probed without a
real key); field parsing follows each vendor's published docs and degrades to
`unknown` if the response shape differs. `codex` 5h/week comes from the local
Codex ChatGPT login and the `chatgpt.com/backend-api/wham/usage` endpoint.

GET /usage returns token counters from local native coding-agent logs. Rinq
reads only structured usage metadata; it does not retain prompt text, assistant
responses, tool arguments, or tool output. Browser and web-app sessions are not
included.

The response contains today, a rolling week, one daily record per day, an apps
breakdown, and discovered sources. The counters are inputTokens,
outputTokens, cachedInputTokens, cacheWriteInputTokens, reasoningOutputTokens,
totalTokens, and requests.

The default sources are ~/.codex/sessions, ~/.trae/cli/sessions,
~/.claude/projects, and ~/.zcode/cli/log. Set CODEX_HOME, TRAE_HOME/TRAECLI_HOME,
CLAUDE_CONFIG_DIR, or ZCODE_HOME when a client stores logs elsewhere. Rinq
reads only structured token counters from ZCode logs and uses an incremental
index under ~/.rinq/usage.sqlite3; it does not retain prompts, responses, tool
arguments, or credential values.
Optional usage.extraSources entries can add another supported local log root
with an adapter and path.
