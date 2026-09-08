# Rinq

Turn an Apple Watch into a glanceable "token battery" dashboard. Like the
Activity rings, but each ring is an AI vendor quota (5h window, weekly window,
API spend budget). When you take the watch off and set it on its charger, it
becomes a desktop status board for the AI work running on your Mac.

```
Mac collector (this repo)  --HTTPS/JSON-->  watchOS app + WidgetKit rings
   hooks (TraeX/Codex)  ------------------->  push notifications (APNs)
```

## What works in this scaffold

- `rinq` Mac CLI/daemon (Python 3, stdlib only):
  - aggregates quota rings + agent events into one status document
  - local HTTP server serves the status JSON
  - hook ingestion for TraeX (`Stop`/`Notification`) and Codex (`notify`)
  - break/focus timer (50/10)
  - collectors: `mock` (on by default), `openai` (real `/organization/costs`),
    `codex` and `anthropic` are stubbed with a documented interface
- watchOS app + WidgetKit ring complication (XcodeGen project), builds for the
  watch simulator. Reads a status endpoint, falls back to bundled sample data.

## Hard constraints this design respects

- macOS cannot push to a watch over Bluetooth. `WatchConnectivity` is
  iPhone<->watch only; watchOS bans background BLE data streams. Transport is
  HTTPS (status pull) + APNs (event push). The watch polls for rings; events
  are pushed.
- A custom app cannot stay always-on while charging. Rings live in the
  **watch face complication**, not a foreground app. Turn off
  `Settings > General > Nightstand Mode` so the watch face shows on the charger.
- There is no "download a .app from GitHub" for watchOS. Distribution is
  TestFlight/App Store (paid account) or Xcode sideload (7-day, free). This
  repo makes the **Mac** side one-command; the watch build is `make watch-build`.

## Quick start (Mac side)

```bash
cd rinq
./install.sh              # installs rinq CLI + launchd agent + hooks
rinq status          # print current aggregated status
rinq serve           # run the local HTTP API (launchd does this for you)
rinq push --state completed --title "build passed"
rinq break           # show focus/break countdown
```

The daemon listens on `127.0.0.1:7788`:

- `GET  /status`                aggregated rings + events
- `POST /event`                hook ingestion `{source,state,title,detail}`
- `POST /mock`                 feed a fake status (watch simulator testing)

## Watch side

```bash
make watch-generate         # xcodegen
make watch-build            # build for watch simulator
make watch-sim              # boot simulator + install + launch
```

Point the app at your Mac's status URL (or the relay URL once deployed). On the
simulator it uses bundled sample data so the rings render with zero setup.

## Layout

```
mac/rinq/      Mac CLI, collectors, HTTP server, hooks
watch/             watchOS app + WidgetKit ring widget (XcodeGen)
schema/            shared status JSON schema
```

See `schema/status.md` for the ring/event contract.

## Hooking agents

TraeX — merge `hooks/traex.hooks.json` into your user `hooks.json` (or the
project `.trae/hooks.json`). Then confirm with `/hooks` inside TraeX.

Codex CLI — append the line in `hooks/codex.notify.toml.snippet` to
`~/.codex/config.toml`.

Manual event (works without hooks):

```bash
rinq push --state started   --title "noteone build"
rinq push --state waiting   --title "noteone build" --detail "needs approval"
rinq push --state completed --title "noteone build" --detail "42 tests passed"
```

## Real watch deploy

The simulator build needs no signing. A physical watch needs a team:

- Free Apple ID: open `watch/Rinq.xcodeproj` in Xcode, set your Personal
  Team on both targets, run to the watch. Re-signs every 7 days; no APNs.
- Paid Apple Developer Program: set `DEVELOPMENT_TEAM` in `watch/project.yml`,
  regenerate, then one command builds + installs over the network:

```bash
make watch-generate
xcodebuild -project watch/Rinq.xcodeproj -scheme RinqWatch \
  -destination 'platform=watchOS,name=<your watch>' build
```

Then on the watch: set the watch face to a modular/Utility face, add the
Rinq complication (the circular gauge renders the rings). Turn off
`Settings > General > Nightstand Mode` so the face shows while charging. Point
the app at your Mac's reachable HTTPS status URL (the relay), or leave the
sample data.

## Data sources

`~/.rinq/config.json` controls collectors. By default the real collectors are
on and auto-discover credentials:

```json
{
  "collectors": ["codex", "minimax", "deepseek", "openai", "anthropic", "moonshot", "zhipu", "xiaomi"],
  "budgetUsd": { "openai": 20.0, "anthropic": 20.0 },
  "balanceFull": { "deepseek": 100.0, "moonshot": 100.0, "zhipu": 100.0 }
}
```

Set `"collectors": ["mock"]` for synthetic demo data with no network calls.

Two ring semantics:

- **window / budget** (subscription quota, postpaid spend) — the ring fills as
  you *consume*. `window` = rate-limit window (5h/week); `budget` = USD spend
  vs a monthly cap.
- **balance** (prepaid CNY balance on Chinese vendors) — the ring fills like a
  battery with *remaining* balance. Set `balanceFull.<vendor>` to a typical
  top-up amount to get a fill level; without it the watch shows the absolute
  ¥ amount on a grey ring.

Credential discovery (`mac/rinq/sources.py`):

- **codex** and **minimax** / **deepseek** need no env setup. Rinq reads your
  local **cc-switch** database (`~/.cc-switch/cc-switch.db`) for API keys and
  your Codex ChatGPT login (`~/.codex/auth.json`) for the OAuth access token.
  Override paths with `RINQ_CCSWITCH_DB` / `RINQ_CODEX_AUTH`.
- Other vendors read env keys (`launchctl setenv KEY value` or the launchd
  environment) and show `unknown` until a key is present. Never commit keys.

| collector | credential | source | status |
| --- | --- | --- | --- |
| `codex` | ChatGPT OAuth (`auth.json`) | `chatgpt.com/backend-api/wham/usage` | live: 5h + week `used_percent` |
| `minimax` | cc-switch key | `api.minimaxi.com/v1/api/openplatform/coding_plan/remains` | live: 5h + week remaining% |
| `deepseek` | cc-switch / `DEEPSEEK_API_KEY` | `api.deepseek.com/user/balance` | live: CNY balance |
| `openai` | `OPENAI_ADMIN_KEY` | `/v1/organization/costs` | live |
| `moonshot` (Kimi) | `MOONSHOT_API_KEY` | `api.moonshot.cn/v1/users/me/balance` | route verified, field best-effort |
| `zhipu` (GLM) | `ZHIPU_API_KEY` | `open.bigmodel.cn/api/monitor/usage/quota/limit` | route verified, field best-effort |
| `xiaomi` (MiMo) | `XIAOMI_API_KEY` | no confirmed public route | shows unknown |
| `anthropic` (Claude) | `ANTHROPIC_ADMIN_KEY` | Admin Usage & Cost API (org only) | interface stub |

MiniMax and Codex return real subscription *windows* (5-hour and weekly), not
prepaid balances, so they render as `window` rings. Endpoints that returned
`401` to an unauthenticated probe are confirmed auth-gated; field parsing
follows each vendor's response and degrades to `unknown` if the shape differs.



