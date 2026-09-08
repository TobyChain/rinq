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

## Vendors and credentials

| collector | env var | endpoint (base) | kind | verified |
| --- | --- | --- | --- | --- |
| `openai` | `OPENAI_ADMIN_KEY` | `/v1/organization/costs` | budget | route+shape |
| `deepseek` | `DEEPSEEK_API_KEY` | `api.deepseek.com/user/balance` | balance | route (401), shape per docs |
| `moonshot` (Kimi) | `MOONSHOT_API_KEY` | `api.moonshot.cn/v1/users/me/balance` | balance | route (401), shape best-effort |
| `zhipu` (GLM) | `ZHIPU_API_KEY` | `open.bigmodel.cn/api/paas/v4/...` | balance | route (401), shape best-effort |
| `minimax` | `MINIMAX_API_KEY` | no public balance route | balance | stub → unknown |
| `xiaomi` (MiMo) | `XIAOMI_API_KEY` | no confirmed public route | balance | stub → unknown |
| `anthropic` (Claude) | `ANTHROPIC_ADMIN_KEY` | Admin Usage & Cost API (org only) | budget | interface only |

"route (401)" means the endpoint exists and is auth-gated (probed without a
real key); field parsing follows each vendor's published docs and degrades to
`unknown` if the response shape differs. `codex` 5h/week comes from the Codex
app-server `account/rateLimits/read`, not an HTTP key.
