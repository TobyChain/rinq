# Rinq AI 接手指南

本文件是新 AI 会话进入 Rinq 仓库后的必读入口。它只保存长期有效的项目约束、当前架构边界和验证入口。不要在这里堆积任务流水账、临时状态或已经失效的实现细节。

## 开始工作前

1. 先读本文件。
2. 读 `README.md` 和与任务直接相关的源码；涉及接口契约时同时读 `schema/status.md`。
3. 读 `docs/architecture.md`，再按任务读取 `docs/subsystems/` 或 `docs/cookbook/` 中已有的相关文档。空文件或空目录表示文档尚未建立，不代表对应设计不存在。
4. 在 `.agents/notes/` 中按关键词查找相关决策记录。只读取与当前任务有关的记录，不要把历史做法自动当成当前事实。
5. 运行 `git status --short --branch`，保留用户已有改动，不覆盖、不清理无关文件。
6. 先从当前源码验证事实。README、docs、notes 与代码冲突时，以可执行源码和测试为准，并在本次改动中修正已经失真的当前态文档。

## 项目定位

Rinq 是本地优先的 AI 配额和本地编码 Agent 用量监视器。它把提供商限额、API 余额和本地结构化 token 计数统一显示为 `used / total` 配额，并提供 macOS 菜单栏、iPhone、iPad、Apple Watch、Widget 和 Complication 界面。

项目有两条独立数据路径：

- macOS 路径：Python daemon 采集配额、本地 token 用量和 Agent 事件，通过 loopback HTTP API 提供给 Swift 菜单栏应用和本地 dashboard。
- Apple 移动端路径：iOS/watchOS 客户端直接访问已配置的提供商 HTTPS 接口，不依赖 Mac daemon；状态缓存供 Widget/Complication 使用。

不要把提供商配额和本地 token 用量混为一谈。前者来自提供商接口，后者来自本机 Agent 日志中的结构化计数字段。

## 当前代码地图

- `mac/rinq/`：Python daemon、CLI、HTTP API、配置、状态、提供商采集、本地用量索引、IDE 集成、事件和 push。
- `mac/RinqMenu/`：macOS 13+ SwiftUI 菜单栏客户端。`Store.swift` 是 daemon API 与 UI 状态的边界，`AppMain.swift` 驱动 30 秒刷新和菜单栏渲染，`QuotaAlerts.swift` 负责配额告警状态。
- `app/Shared/`：iOS/watchOS 共用模型、视图、设置和直接提供商采集。
- `app/iOS/`、`app/Watch/`：应用入口。
- `app/iOSWidget/`、`app/WatchWidget/`：Widget 和 Complication。
- `app/project.yml`：Apple 多目标工程的权威配置；`app/Rinq.xcodeproj/` 是生成物并被忽略。
- `schema/status.md`：跨进程、跨界面的公开 JSON 契约。
- `hooks/`：TraeX 和 Codex 通知接入示例。
- `install.sh`、`mac/com.rinq.menu.plist`：本地安装和 launchd 部署。
- `mac/test_rinq.py`、`mac/RinqMenu/Tests/`：Python 和 macOS Swift 的现有测试入口。

## 模块 Seam

这里的 Seam 指稳定边界，不要求引入额外框架。修改某一侧时，先确认所有生产者、消费者和契约测试。

| Seam | Provider / 生产者 | Consumer / 消费者 | 稳定边界 |
| --- | --- | --- | --- |
| 配额采集 | `mac/rinq/collectors.py`；移动端 `app/Shared/Providers.swift` | `/status`、macOS UI、Apple UI | ring 字段和不可用状态 |
| daemon HTTP API | `mac/rinq/server.py` | `mac/RinqMenu/.../Store.swift`、CLI、本地 dashboard | `/status`、`/usage`、`/config`、`/integrations`、`/event`、`/auth/connect` |
| 配置 | `mac/rinq/config.py`、`settings_api.py` | collectors、server、macOS Settings | 公共配置不得回传明文密钥 |
| 本地用量采集 | `mac/rinq/usage.py` 的 source adapter 和增量 SQLite 索引 | `/usage`、macOS Usage UI | 只持久化计数和来源元数据 |
| 本地 IDE 集成 | `mac/rinq/integrations.py` | `/config`/`/integrations`、Settings UI | 安装、认证、套餐、实时配额是不同能力状态 |
| Agent 事件 | CLI/hook -> `events.py` -> `state.py` | `/status`、dashboard、push | `started/completed/failed/waiting` |
| Apple 共享模型 | `app/Shared/Models.swift` 和 Provider 输出 | iOS、watchOS、Widget | 与 `schema/status.md` 的 ring 语义一致 |

新增提供商或字段时，不要只修改一个 UI。至少检查 Python collector、移动端直连实现、两套 Swift model、`schema/status.md`、设置界面和相应测试是否需要同步。某个平台明确不支持时，应把差异写入当前态文档，不要制造虚假的对称实现。

## 核心循环

### macOS 配额与界面循环

1. `AppMain.swift` 启动后和每 30 秒调用 `Store.refresh()`。
2. `Store` 并行读取 `/status`、`/config` 和 `/usage`。
3. daemon 的 `build_status()` 加载配置和状态，调用 collector，生成统一 rings，并原子写回状态。
4. `QuotaAlertMonitor` 根据当前 ring 和持久化采样计算告警。
5. 菜单栏绘制紧凑横条；popover 展示 rings、usage 和 settings。新告警可以自动打开 popover。popover 打开后由空闲计时器在 10 秒无交互时自动收起（活动告警期间除外）。

### 本地用量索引循环

1. `usage.py` 发现 Codex、TraeX、Claude Code、ZCode、OMP 及显式追加的日志源。
2. SQLite 保存文件 inode、读取 offset 和结构化 token 事件。
3. 刷新时只继续扫描新增的完整 JSONL 行；文件轮换或截断时重建该文件的索引。
4. `/usage` 从索引派生今日、滚动周、逐日和逐应用汇总。

### iOS/watchOS 直连循环

1. `TRProviders.fetchAll` 对已启用提供商并发请求。
2. 各 adapter 归一化为 `TRRing`。
3. 结果写入 App Group cache。
4. App、Widget 和 Complication 从相同 ring 语义渲染。

## 不可破坏的产品和安全约束

- 配额的持久契约是 `usedValue`、`totalValue`、`valueUnit`；`usedPercent` 只用于归一化渲染，不能替代原始数值。
- 未认证、无稳定接口或无法解析真实配额时，显示明确的灰色 `Not connected`、`Unavailable` 或 `unknown` 状态。不得伪装成 0% 使用量，也不得从套餐价格、授权上限、网页文案或浏览器 cookie 推断实时余额。
- daemon 默认绑定 `127.0.0.1:7788`。配置写入和认证动作只允许 loopback 客户端。若改为 `0.0.0.0`，必须明确说明局域网暴露和无认证风险。
- API key、session credential、`~/.rinq/config.json`、`~/.rinq/usage.sqlite3` 和导出的本地数据库不得提交。公共配置响应不得泄露密钥。
- 本地用量采集只读取结构化计数和必要的来源元数据；不得保存 prompt、response、工具参数、工具输出或浏览器会话。
- OMP 默认从 `~/.omp/agent/sessions` 递归采集主会话和子 Agent 的 assistant usage；尊重 `PI_CODING_AGENT_DIR`，并按稳定 message ID 去重 fork 复制的消息。
- macOS 部署目标是 13。不要无意中引入 macOS 14+ API。
- 告警是用户可见契约。当前快速消耗规则使用 25–45 分钟样本且增量大于 20 个百分点；5 小时窗口剩余量低于 30%、周窗口剩余量低于 10% 时告警；耗尽为 critical。修改阈值前必须同步测试和当前态文档。
- macOS popover 有活动告警时，点击窗口内任意区域即视为确认并消除当前告警；自动弹出本身不能直接消警，子控件仍需执行原有点击行为。
- 清除或 dismiss 告警时，相关 pulse/breathing 动画必须立即停止，不能只隐藏文字。
- 当前 macOS popover 发生过告警后，告警槽位应保留到该窗口关闭；消警不得改变窗口尺寸、圆环直径、配额行高度或内容起点。重新打开无告警窗口时才恢复紧凑布局。
- macOS popover 的实体背景只设置在根内容层；不得递归给 SwiftUI/AppKit 子视图启用 layer 或填充背景，否则文字、SF Symbols 和控件会出现白色矩形底。
- macOS popover 底部常驻一条 footer，内含 `Quit Rinq` 退出按钮（`NSApplication.shared.terminate`）。它在所有标签页可见，其高度是布局固定项。菜单 launch agent 使用 `KeepAlive={SuccessfulExit=false}`，用户主动退出后不重启，崩溃或下次登录仍自启。
- macOS popover 打开后若 10 秒内无窗口内交互（点击、滚动、按键、拖拽、指针移动）则自动收起。任何窗口内交互都重置该计时。存在活动告警时不自动收起，告警消除后重新计时。收起或关闭 popover 时必须取消计时器并移除事件监视器，不得泄漏。
- token hover 格式保持一位小数：低于 `0.1M` 使用 `K`，之后使用 `M`，达到十亿使用 `B`。
- 提供商端点和响应结构会漂移。修改 adapter 前核对当前官方接口；失败必须降级为显式不可用状态，不得展示陈旧值为成功。
- 安装脚本会写入 `~/.rinq`、`~/.local/bin`、`~/Library/LaunchAgents` 和日志目录，并重载 launchd。除非任务明确要求安装或部署，不要把 `./install.sh` 当作普通验证命令。

## 文档与决策记录

### `docs/`：只记录当前事实

- `docs/architecture.md`：当前整体架构、主要数据流、核心循环和跨模块契约。
- `docs/subsystems/`：单个稳定子系统的当前职责、入口、依赖、状态和失败边界。
- `docs/cookbook/`：当前仍可复现的开发、诊断和发布操作。
- `docs/postmortem/`：为保持目录模板而预留；本仓库当前采用“docs 不保留历史”的规则，历史复盘应写入 `.agents/notes/`，不要在此新增历史叙事。
- 源码 AST 工具、生成规则和代码图谱属于 `docs/`。图谱必须可由当前源码重建，并标注生成命令、范围和时间；源码结构改变后更新或移除失真的图谱。
- docs 只描述当前代码。架构变化时，在同一次改动中更新对应文档；不要把旧方案、迁移流水账、讨论过程或废弃设计留在 docs。

### `.agents/notes/`：append-only 历史记录

- 用于记录非显然问题、方案权衡、失败做法、决策过程、结果和后续风险。普通代码改动不强制创建 note。
- `proposed/`、`implemented/`、`rejected/`、`archived/` 表示新记录写入时的状态。文件名使用 `YYYYMMDD-short-topic.md`。
- 已有 note 不得编辑、覆盖、删除、重命名或移动。状态发生变化时，在新目录中新建一份 note，引用旧 note，并写明新证据和结果。
- note 至少包含 `Problem`、`Decision`、`Alternatives considered`、`Consequences`；只写当时可核验的信息，区分事实、推断和未验证假设。
- notes 不是当前架构真相源。若历史记录与当前源码冲突，保留历史 note，并修正 `docs/` 中的当前态描述。

## 修改原则

- 做满足任务的最小完整改动，不顺手重构无关模块。
- 优先保持现有标准库 Python 和原生 Swift/SwiftUI 方案；引入依赖前说明必要性和部署影响。
- I/O、provider parsing、协议或持久化变化要覆盖成功、缺失凭证、异常响应和不可用状态。
- 变更公开 JSON 时保持兼容；需要破坏兼容时显式提升契约版本，并同步所有消费者。
- 不直接编辑生成的 `app/Rinq.xcodeproj/`；修改 `app/project.yml` 后用 XcodeGen 重建。
- 不提交 `app/build/`、`mac/RinqMenu/.build/`、缓存、日志或本地运行数据。
- 未经明确授权，不发布 release、不推送远端、不运行安装脚本。仓库提交作者使用 `TobyChain <g787796121@163.com>`，不添加 AI attribution 或 `Co-authored-by` trailer。

## 验证

按改动范围运行最小充分验证：

```bash
make mac-test

cd mac/RinqMenu
swift test
swift build -c release

# 仅在对应 Apple 目标受影响且本机有 Xcode/XcodeGen 时
make ios-build
make watch-build
```

涉及 daemon 运行或安装且任务已明确授权时，再验证：

```bash
curl --fail --silent http://127.0.0.1:7788/status
curl --fail --silent http://127.0.0.1:7788/usage
```

结束前检查：

1. 相关测试和构建实际通过；无法运行的检查明确说明原因。
2. `schema/status.md` 和 `docs/` 未因本次实现变成陈旧描述。
3. 没有密钥、本地数据库、构建产物或无关文件进入 Git 变更。
4. `git diff --check` 无空白错误，`git status --short` 只包含任务范围内的改动。
