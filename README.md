# Rinq

🇬🇧 English · [🇨🇳 简体中文](README.zh-CN.md)

Rinq is a glanceable AI quota monitor for Apple devices. It turns provider
limits, balances, and local coding-agent token usage into Activity-style rings
and compact bars.

Rinq has two independent paths:

- iPhone, iPad, and Apple Watch apps fetch configured provider quotas directly
  over HTTPS.
- The optional macOS menu-bar app reads local provider credentials and local
  coding-agent logs through a loopback daemon.

## macOS quick start

The macOS path is the easiest way to try Rinq:

~~~bash
git clone https://github.com/TobyChain/rinq.git
cd rinq
./install.sh
~~~

install.sh installs the rinq CLI, starts the local daemon, builds the menu-bar
app, and registers both as launchd agents. Click the Rinq icon in the menu bar
to open the popover.

The menu-bar app includes:

- Rings: configured provider quotas as adaptive colored rings and bars; click a quota alert banner to dismiss it until that quota condition clears;
- Usage: daily and rolling-week input/output tokens from local coding agents; hover a daily bar group to see that day's exact input and output counts;
- Providers: local credential setup, vendor toggles, and drag-to-reorder.

The daemon listens on 127.0.0.1:7788 by default. Useful local endpoints are
/status, /usage, and /config. The detailed JSON contracts are in
[schema/status.md](schema/status.md).

To update an existing installation:

~~~bash
git pull
./install.sh
~~~

## Local token usage

The macOS Usage tab reads structured token counters from native local coding
agents. It does not read browser sessions and does not store prompts,
responses, tool arguments, or tool output.

Default log locations:

- Codex: ~/.codex/sessions
- TraeX: ~/.trae/cli/sessions
- Claude Code: ~/.claude/projects

Rinq supports CODEX_HOME, TRAE_HOME, TRAECLI_HOME, and CLAUDE_CONFIG_DIR for
non-standard locations. The incremental index is stored locally at
~/.rinq/usage.sqlite3; seven days are scanned by default.

Local usage is separate from provider subscription quota. A token counter can
exist even when a provider does not expose a public quota endpoint.

## Provider quotas

The current collectors cover:

| Provider | Displayed data | Credential source |
| --- | --- | --- |
| ChatGPT / Codex | 5-hour and weekly windows | Local Codex login |
| MiniMax | Coding Plan 5-hour and weekly windows | API key or cc-switch |
| OpenAI API | Organization spend | Admin API key |
| DeepSeek | Balance | API key or cc-switch |
| Kimi / Moonshot | Balance | API key |
| GLM / Zhipu | Balance | API key |
| Xiaomi MiMo | Balance when a supported endpoint is available | API key |
| Claude API | Organization spend when configured | Admin API key |

Providers without a usable credential are hidden. All values use the same
direction: used / total. Balance rings use the configured balanceFull value as
their reference total.

macOS provider settings are stored locally in ~/.rinq/config.json with
restrictive file permissions. Rinq sends credentials only to the matching
provider endpoint. Do not commit ~/.rinq/config.json or any API key.

## iOS and watchOS

The Apple apps are source-only and do not require a Mac at runtime. They share
the provider models and ring views, and include an iOS widget plus a watchOS
complication.

Generate the Xcode project and build for simulators:

~~~bash
make ios-build
make watch-build
~~~

For a physical device, open the generated app/Rinq.xcodeproj in Xcode and
select your development team. A free Apple ID is suitable for local testing
but requires periodic re-signing; a paid team is needed for longer-lived
device installs and iCloud Keychain sharing.

The ChatGPT/Codex collector uses an unofficial endpoint and is intended for
self-built or sideloaded builds. Do not include it in an App Store build.

## Configuration

The macOS daemon creates ~/.rinq/config.json on first run. A minimal example:

~~~json
{
  "collectors": ["codex", "minimax", "deepseek", "openai"],
  "budgetUsd": { "openai": 20.0 },
  "balanceFull": { "deepseek": 100.0 },
  "usage": { "lookbackDays": 7 }
}
~~~

Set `collectors` to ["mock"] to show synthetic data without provider network
requests. Use `usage.extraSources` only when a supported coding agent stores its
JSONL logs outside the standard directories.

## Development

~~~bash
cd mac
python3 -m unittest test_rinq

cd RinqMenu
swift test
swift build -c release
~~~

The repository also contains the iOS/watchOS source, provider adapters, local
hooks, and the public status schema. Contributions should keep credentials
local, preserve explicit offline/error states, and avoid adding provider-
specific secrets to source control.

## License

Rinq is licensed under the [Apache License 2.0](LICENSE).
