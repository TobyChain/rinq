# Rinq

[🇬🇧 English](README.md) · 🇨🇳 简体中文 · [许可证](#许可证)

## TL;DR

**在额度或本地 Agent 用量影响工作之前，一眼看到问题。**

Rinq 是面向 Apple 设备的 AI 用量监控应用。它将厂商限额、API 余额，以及本地 Codex、TraeX、Claude Code、OMP 的 token 计数，统一显示为活动圆环、紧凑进度条和每日用量摘要。

macOS 菜单栏应用是最快的使用方式：一个脚本会安装本地 daemon、CLI 和原生弹窗。iPhone、iPad、Apple Watch、小组件和 complication 以源码提供，可在没有 Mac 中转的情况下直接获取受支持的厂商额度。

## 项目简介

AI 用量分散在订阅时间窗、API 余额和本地 Agent 日志中，每类数据的单位与重置规则都不同，用户往往在任务中断后才发现额度问题。Rinq 将这些信号统一为 `used / total` 视图，同时让厂商凭据和本地 token 历史留在设备上。

Rinq 包含两条相互独立的数据路径：

- **厂商额度**：Apple 客户端或 macOS collector 通过 HTTPS 调用已配置的厂商接口。
- **本地 token 用量**：macOS daemon 增量读取原生 coding agent 日志中的结构化计数。

## Rinq 提供什么

| 能力 | 作用 |
|---|---|
| **额度圆环** | 每条厂商横栏右侧显示独立圆环，以 `used / total` 呈现订阅时间窗、消费金额和余额 |
| **Agent 会话** | 按 CLI 分组展示运行、子 Agent 运行、等待和空闲状态，以及项目、模型、路径和最近摘要 |
| **可处理的告警** | 标记额度耗尽、低余额和短时快速消耗；点击告警后隐藏，直到该额度状态恢复 |
| **本地用量** | 汇总每天和滚动一周的 input/output tokens，不保存 prompt 或响应正文 |
| **逐日查看** | 悬停每日柱组，以保留一位小数的 K/M/B 单位显示当天 input/output |
| **Apple 多端** | macOS 菜单栏、iPhone、iPad、Apple Watch、iOS 小组件和 watchOS complication 共享同一套圆环模型 |
| **厂商控制** | 在本机管理凭据、连接状态、按厂商取消额度跟踪、参考总额和圆环顺序 |

## 工作原理

```text
厂商 HTTPS API ───────────────────┐
                                 ├─ 标准化额度圆环 ─────┐
本地 coding-agent JSONL 日志 ─┐  │                     │
                              ├─ macOS 回环 daemon ────┼─ 菜单栏 + 本地 Dashboard
~/.rinq/usage.sqlite3 ────────┘                        │
                                                       └─ status / usage JSON

iPhone · iPad · Apple Watch ── 厂商 HTTPS 直连 ── 共享圆环视图
```

本地 token 用量与厂商订阅额度始终是两类数据。即使厂商没有公开额度接口，Rinq 仍然可以统计本地 coding agent 产生的 token。

## 快速开始

### 环境要求

- 使用菜单栏应用和本地用量采集时需要 macOS
- daemon 和 CLI 需要 Python 3
- 原生菜单栏应用需要 Swift 工具链或 Xcode Command Line Tools

### 在 macOS 安装

#### 通过 Release DMG 安装（无需克隆仓库）

从 [Releases](https://github.com/TobyChain/rinq/releases) 下载 `RinqMenu-<版本>-arm64.dmg`，打开后把 Rinq 拖入 Applications。首次启动时应用会自动把 daemon 和 `rinq` CLI 安装到 `~/.rinq` 并注册 launchd 服务，无需其他步骤。DMG 为 ad-hoc 签名：首次启动若遇到 Gatekeeper 提示，右键点击应用选择"打开"即可。

#### 通过仓库安装

```bash
git clone https://github.com/TobyChain/rinq.git
cd rinq
./install.sh
```

安装脚本会把运行时代码复制到 `~/.rinq`，安装 `~/.local/bin/rinq`，构建原生菜单栏应用，并将 daemon 与菜单应用注册为 launchd 服务。仓库安装不会被 DMG 应用修改；若想让应用接管 daemon 管理，删除 `~/.rinq/libexec` 后重新启动应用即可。点击菜单栏中的 Rinq 图标即可打开弹窗。

弹窗包含三个页面：

- **Rings**：每个 provider 一条横栏、右侧独立圆环，显示重置时间窗和可点击消除的告警；横栏上方是本地 Agent 会话状态条（运行中、等待审批、空闲）。
- **Usage**：显示今日、滚动一周、逐日 input/output 和分应用汇总。
- **Providers**：管理本地凭据、自动激活状态、按厂商取消额度跟踪和拖拽排序。

弹窗底部的 footer 有一个 **Quit Rinq** 按钮，用于退出菜单栏应用。弹窗打开后若 10 秒内无交互会自动收起；在其中点击、滚动、按键或移动指针都会重置计时，存在活动告警时保持展开直到被确认。

更新已有安装：

```bash
git pull --ff-only
./install.sh
```

daemon 默认监听 `127.0.0.1:7788`。主要本地接口为 `/status`、`/usage` 和 `/config`。

## 支持的厂商额度

| 厂商 | 显示内容 | 凭据来源 |
|---|---|---|
| ChatGPT / Codex | 5 小时和周限额 | 本地 Codex 登录 |
| MiniMax | Coding Plan 5 小时和周限额 | API Key 或 cc-switch |
| OpenAI API | 组织级消费金额 | Admin API Key |
| DeepSeek | 余额 | API Key 或 cc-switch |
| Kimi / Moonshot | 余额 | API Key |
| GLM / 智谱 | Coding Plan 限额，或预付余额 | API Key |
| Jina AI | 共享 token 池剩余量 | API Key |
| 小米 MiMo | 暂不支持 | API Key |
| Claude API | 暂不支持 | Admin API Key |

保存 API key 或检测到受支持的账户后，厂商自动激活，无需额外开关。之后可以在该厂商的 Providers 行里点击 **Stop tracking** 取消额度跟踪：凭据保留，Rinq 停止抓取并隐藏其圆环；点击 **Resume tracking** 或重新保存 key 即可恢复。没有可用凭据的厂商不会显示。余额类圆环使用配置中的 `balanceFull` 作为参考总额。GLM 的 Coding Plan Key 显示滚动的 5 小时和周请求限额，按量付费 Key 则回退为预付余额。Jina 显示其 Embeddings/Reranker/Reader/Search 共享 token 池；dashboard 主机由 `hosts.jina` 或 `JINA_DASHBOARD_HOST` 配置（默认 `embeddings-dashboard-api.jinaai.cn`，国际站用 `embeddings-dashboard-api.jina.ai`）。小米 MiMo 和 Claude API 暂无可用的实时额度接口，存在凭据时显示明确的“暂不支持”卡片。ChatGPT/Codex 依赖非官方订阅接口，仅适用于自行构建或侧载的应用，不应进入 App Store 构建。

## 本地 token 用量

macOS Usage 页面读取原生本地 Agent 产生的结构化 token 计数。它不读取浏览器会话，也不保存 prompt、响应内容、工具参数或工具输出。

默认目录：

- Codex：`~/.codex/sessions`
- TraeX：`~/.trae/cli/sessions`
- Claude Code：`~/.claude/projects`
- OMP / oh-my-pi：`~/.omp/agent/sessions`
- Pi：`~/.pi/agent/sessions`

Rinq 支持 `CODEX_HOME`、`TRAE_HOME`、`TRAECLI_HOME`、`CLAUDE_CONFIG_DIR`、`ZCODE_HOME`、OMP 的 `PI_CODING_AGENT_DIR` 和 Pi 的 `PI_AGENT_DIR`。如果受支持的 Agent 将 JSONL 日志存放在其他目录，可配置 `usage.extraSources`。增量索引位于 `~/.rinq/usage.sqlite3`，默认查看最近 7 天。

## 实时 Agent 会话

Rings 页面和网页 dashboard 顶部展示 Claude Code、Codex、TraeX、OMP、Pi 仍打开的终端会话。会话先按 CLI 分组，再按运行中、子 Agent 运行中、等待审批、空闲排序；每行显示项目、模型、工作目录、最近摘要和更新时间。收到 `SessionEnd` 后会话自动消失；没有关闭 hook 时，空闲或等待活动最多保留 10 分钟，运行中的 shell 和子 Agent 有 15 分钟宽限期；这时依据日志推断可见性，不检查终端进程。数据由 `GET /sessions` 提供，只在内存中从日志尾部重建，Rinq 不持久化任何 prompt 或助手回复（见[状态契约](schema/status.md#local-agent-sessions)）。

不装 hook 时，状态依据日志活动（未闭合的工具调用、回合结束、错误）和短宽限时间推断。Claude Code 和 TraeX 的通知 hook 可直接上报等待状态；Codex notify 只上报回合完成，其余状态仍依据日志推断：

| Agent | Hook 文件 | 安装位置 |
|---|---|---|
| Claude Code | [hooks/claude.settings.snippet.json](hooks/claude.settings.snippet.json) | 合并到 `~/.claude/settings.json` |
| Codex CLI | [hooks/codex.notify.toml.snippet](hooks/codex.notify.toml.snippet) | 将 `notify` 行加入 `~/.codex/config.toml` |
| TraeX | [hooks/traex.hooks.json](hooks/traex.hooks.json) | TraeX hooks 配置 |

Hook 只向本机 daemon 发送事件，只持久化生命周期状态和安全元数据，不保存 prompt、回复、title 或 detail 文本。`SessionEnd` 会清除打开会话。原生弹窗和网页面板每 2 秒独立刷新会话，日志扫描缓存 5 秒，hook 事件会立即使缓存失效。也可以手动记录：`rinq push --state waiting --title "review needed" --session-id claude:abc --cwd ~/code/x`。

Providers 页面列出检测到的 IDE，每个都可以 **Stop monitoring**，右上角的 **Refresh** 按钮会重新扫描本机。取消监控后 Rinq 不再探测该 IDE，只保留一行身份信息，可以随时恢复。集成能力按证据分级：ZCode 当前可以读取本地 OAuth/套餐状态和结构化 token 用量，但套餐 entitlement 本身不能作为已用/剩余额度圆环；MiMo Code/Desktop 和 Trae CN 可以检测安装状态，个人订阅余额在厂商提供稳定官方接口前保持 `unknown`。Copilot、Cursor、Windsurf、Gemini Code Assist、Zed、Cline、Roo Code 和 Kilo Code 也遵循同一规则，不从套餐价格、网页文字、浏览器 Cookie 或未公开接口推断实时剩余额度。

## 配置

macOS daemon 首次运行时会创建 `~/.rinq/config.json`。最小配置示例：

```json
{
  "collectors": ["codex", "minimax", "deepseek", "openai"],
  "budgetUsd": { "openai": 20.0 },
  "balanceFull": { "deepseek": 100.0 },
  "usage": { "lookbackDays": 7 }
}
```

将 `collectors` 设置为 `["mock"]`，可以在不请求厂商网络接口的情况下显示模拟数据。

## iOS 和 watchOS

Apple 端应用以源码形式提供，运行时不依赖 Mac。iOS 和 watchOS 共享厂商模型和圆环视图，并包含 iOS 小组件及 watchOS complication。

```bash
make ios-build
make watch-build
```

如需安装到实体设备，请在 Xcode 中打开 `app/Rinq.xcodeproj` 并选择自己的开发团队。免费 Apple ID 可用于本地测试，但需要定期重签；长期安装和 iCloud Keychain 共享需要付费开发者团队。

## 存储与安全

- 厂商设置存储在本机 `~/.rinq/config.json`，文件使用受限权限。
- 用量索引位于 `~/.rinq/usage.sqlite3`，只保存计数和来源元数据，不保存对话内容。
- 凭据只会发送到对应厂商的接口。
- daemon 默认只监听回环地址，配置写入仅接受本机客户端。
- 不要提交 `~/.rinq/config.json`、API Key、会话凭据或导出的本地数据库。

## 文档

| 文档 | 内容 |
|---|---|
| [状态契约](schema/status.md) | 公开的额度、事件和本地用量 JSON 契约 |
| [English README](README.md) | 英文项目指南 |
| [Hooks](hooks/) | Agent 通知集成示例 |
| [Apple 工程](app/project.yml) | iOS/watchOS targets 和构建配置 |

## 开发

运行 daemon 和原生菜单栏测试：

```bash
cd mac
python3 -m unittest test_rinq

cd RinqMenu
swift test
swift build -c release
```

仓库还包含厂商适配器、本地 hooks、iOS/watchOS 源码、小组件和公开状态契约。修改应保持凭据仅存于本地、明确显示离线/错误状态，并维持统一的 `used / total` 额度契约。

## 项目状态

Rinq 是个人开源项目。厂商额度能力取决于各厂商公开的接口；非官方或仅面向组织的端点可能独立变化。

## 许可证

Rinq 采用 [Apache License 2.0](LICENSE)。
