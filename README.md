# Rinq

🇬🇧 English · [🇨🇳 简体中文](README.zh-CN.md) · [License](#license)

## TL;DR

**See AI quota and local coding-agent usage before either becomes a problem.**

Rinq is a glanceable AI usage monitor for Apple devices. It turns provider limits, API balances, and local Codex, TraeX, and Claude Code token counters into Activity-style rings, compact bars, and daily usage summaries.

The macOS menu-bar app is the fastest way to start: one script installs a loopback daemon, CLI, and native popover. iPhone, iPad, Apple Watch, widgets, and complications are available from source and can fetch supported provider quotas without a Mac.

## Introduction

AI usage is fragmented across subscription windows, API balances, and local agent logs. Each source uses different units and reset rules, so users often discover a limit only after work stops. Rinq normalizes these signals into one `used / total` view while keeping provider credentials and local token history on the device.

Rinq has two independent data paths:

- **Provider quota:** Apple clients or the macOS collector call configured provider endpoints over HTTPS.
- **Local token usage:** the macOS daemon incrementally reads structured counters from native coding-agent logs.

## What Rinq Adds

| Area | What changes |
|---|---|
| **Quota rings** | Provider windows, spend, and balances use a common `used / total` presentation |
| **Actionable alerts** | Exhausted, low, or rapidly consumed quota is highlighted; clicking the alert dismisses it until that condition clears |
| **Local usage** | Daily and rolling-week input/output tokens are aggregated without storing prompts or responses |
| **Daily inspection** | Hovering a day shows its input and output counts in one-decimal K/M/B units |
| **Apple surfaces** | macOS menu bar, iPhone, iPad, Apple Watch, iOS widget, and watchOS complication share the same ring model |
| **Provider controls** | Credentials, vendor visibility, reference totals, and ring order are managed locally |
| **IDE integrations** | Detect installed/running coding IDEs, local account state, and structured local usage |

## How It Works

```text
Provider HTTPS APIs ───────────────┐
                                   ├─ normalized quota rings ─┐
Local coding-agent JSONL logs ─┐   │                          │
                               ├─ macOS loopback daemon ──────┼─ menu bar + local dashboard
~/.rinq/usage.sqlite3 ─────────┘                              │
                                                             └─ status / usage JSON

iPhone · iPad · Apple Watch ─── direct provider HTTPS ─── shared ring views
```

Local token usage and provider quota remain separate. Rinq can show local agent usage even when a provider does not expose a public quota endpoint.

## Getting Started

### Requirements

- macOS for the menu-bar app and local usage collector
- Python 3 for the daemon and CLI
- Swift toolchain/Xcode Command Line Tools for the native menu-bar app

### Install on macOS

```bash
git clone https://github.com/TobyChain/rinq.git
cd rinq
./install.sh
```

The installer copies the runtime to `~/.rinq`, installs `~/.local/bin/rinq`, builds the native menu-bar app, and registers both the daemon and menu app with launchd. Click the Rinq menu-bar icon to open the popover.

The popover contains:

- **Rings:** configured quotas, reset windows, and dismissible alerts.
- **Usage:** today, rolling week, per-day input/output, and per-app totals.
- **Providers:** local credentials, vendor toggles, and drag-to-reorder.

Update an existing installation:

```bash
git pull --ff-only
./install.sh
```

The daemon listens on `127.0.0.1:7788` by default. Useful local endpoints are `/status`, `/usage`, and `/config`.

## Provider Quotas

| Provider | Displayed data | Credential source |
|---|---|---|
| ChatGPT / Codex | 5-hour and weekly windows | Local Codex login |
| MiniMax | Coding Plan 5-hour and weekly windows | API key or cc-switch |
| OpenAI API | Organization spend | Admin API key |
| DeepSeek | Balance | API key or cc-switch |
| Kimi / Moonshot | Balance | API key |
| GLM / Zhipu | Balance | API key |
| Xiaomi MiMo | Balance when a supported endpoint is available | API key |
| Claude API | Organization spend when configured | Admin API key |

Providers without a usable credential are hidden. Balance rings use the configured `balanceFull` value as their reference total. ChatGPT/Codex relies on an unofficial subscription endpoint and is intended for self-built or sideloaded apps, not App Store distribution.

## Local Token Usage

The macOS Usage tab reads structured token counters from native local agents. It does not read browser sessions or retain prompts, responses, tool arguments, or tool output.

Default locations:

- Codex: `~/.codex/sessions`
- TraeX: `~/.trae/cli/sessions`
- Claude Code: `~/.claude/projects`

Rinq honors `CODEX_HOME`, `TRAE_HOME`, `TRAECLI_HOME`, `CLAUDE_CONFIG_DIR`, and `ZCODE_HOME`. Use `usage.extraSources` when a supported agent stores JSONL logs elsewhere. The incremental index lives at `~/.rinq/usage.sqlite3`; the default lookback is seven days.

The macOS Providers tab also detects installed and running coding IDEs such as ZCode, MiMo Code/Desktop, and Trae CN. It reports the IDE's non-secret login/entitlement state and can open the vendor's official account connection page. Rinq never asks for a vendor password, reads browser cookies, or copies encrypted client credentials into `~/.rinq/config.json`.

Integration support is capability-aware. ZCode currently exposes local OAuth/plan metadata and structured token usage; its entitlement endpoint does not by itself provide a valid used/remaining ring. MiMo Code/Desktop and Trae CN are detected when installed, while their personal subscription balances remain `unknown` until a stable official usage interface is available. The same policy applies to Copilot, Cursor, Windsurf, Gemini Code Assist, Zed, Cline, Roo Code, and Kilo Code.

## Configuration

The daemon creates `~/.rinq/config.json` on first run. A minimal configuration is:

```json
{
  "collectors": ["codex", "minimax", "deepseek", "openai"],
  "budgetUsd": { "openai": 20.0 },
  "balanceFull": { "deepseek": 100.0 },
  "usage": { "lookbackDays": 7 }
}
```

Set `collectors` to `["mock"]` to render synthetic data without provider network requests.

## iOS and watchOS

The Apple apps are source-only and do not require a Mac at runtime. They share provider models and ring views and include an iOS widget plus a watchOS complication.

```bash
make ios-build
make watch-build
```

For a physical device, open `app/Rinq.xcodeproj` in Xcode and select your development team. A free Apple ID works for local testing but requires periodic re-signing; longer-lived installs and iCloud Keychain sharing require a paid team.

## Storage and Security

- Provider settings are stored locally in `~/.rinq/config.json` with restricted permissions.
- The usage index is local at `~/.rinq/usage.sqlite3` and stores counters and source metadata, not conversation content.
- Credentials are sent only to their matching provider endpoint.
- The daemon binds to the loopback interface by default; configuration writes are restricted to local clients.
- Do not commit `~/.rinq/config.json`, API keys, session credentials, or exported local databases.

## Documentation

| Document | Purpose |
|---|---|
| [Status schema](schema/status.md) | Public quota, event, and local usage JSON contracts |
| [Chinese README](README.zh-CN.md) | Simplified Chinese project guide |
| [Hooks](hooks/) | Agent notification integration examples |
| [Apple project](app/project.yml) | iOS/watchOS targets and build configuration |

## Development

Run the daemon tests and native menu-bar tests:

```bash
cd mac
python3 -m unittest test_rinq

cd RinqMenu
swift test
swift build -c release
```

The repository also contains provider adapters, local hooks, iOS/watchOS sources, widgets, and the public status contract. Changes should preserve local credential handling, explicit offline/error states, and the common `used / total` quota contract.

## Project Status

Rinq is a personal open-source project. Provider quota support depends on the interfaces each provider exposes; unofficial or organization-only endpoints may change independently of Rinq.

## License

Rinq is licensed under the [Apache License 2.0](LICENSE).
