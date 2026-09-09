# Rinq

[🇬🇧 English](README.md) · 🇨🇳 简体中文

Rinq 是一个面向 Apple 设备的 AI 额度监控应用。它把各个 AI 厂商的订阅
限额、API 余额和本地 coding agent 的 token 用量，转换成类似 Apple「活动」
圆环的可视化信息。

Rinq 提供两条相互独立的使用路径：

- iPhone、iPad 和 Apple Watch 应用通过 HTTPS 直接获取已配置的厂商额度；
- 可选的 macOS 菜单栏应用通过本地 daemon 读取凭据和本地 coding agent 日志。

## macOS 快速开始

macOS 路径适合第一次体验 Rinq：

~~~bash
git clone https://github.com/TobyChain/rinq.git
cd rinq
./install.sh
~~~

install.sh 会安装 rinq 命令、启动本地 daemon、构建菜单栏应用，并将两者
注册为 launchd 服务。点击菜单栏中的 Rinq 图标即可打开弹窗。

菜单栏应用包含三个页面：

- Rings：以自适应的彩色圆环和进度条显示已配置的厂商额度；
- Usage：显示本地 coding agent 当日及滚动一周的 input/output tokens；
- Providers：配置本地凭据、启用或隐藏厂商，并拖拽调整圆环顺序。

daemon 默认监听 127.0.0.1:7788。主要本地接口为 /status、/usage 和
/config。完整 JSON 契约见 [schema/status.md](schema/status.md)。

更新已有安装：

~~~bash
git pull
./install.sh
~~~

## 本地 token 用量

macOS 的 Usage 页面读取原生 coding agent 产生的结构化 token 计数。它不读取
浏览器会话，也不会保存 prompt、响应内容、工具参数或工具输出。

默认日志目录：

- Codex：~/.codex/sessions
- TraeX：~/.trae/cli/sessions
- Claude Code：~/.claude/projects

如果客户端使用了其他目录，可以设置 CODEX_HOME、TRAE_HOME、TRAECLI_HOME
或 CLAUDE_CONFIG_DIR。增量索引只保存在本机 ~/.rinq/usage.sqlite3，默认
扫描最近 7 天。

本地用量与厂商订阅额度是两类不同数据。即使厂商没有公开的额度接口，Rinq
仍然可以统计本地 coding agent 产生的 token。

## 支持的厂商额度

当前 collector 覆盖：

| 厂商 | 显示内容 | 凭据来源 |
| --- | --- | --- |
| ChatGPT / Codex | 5 小时和周限额 | 本地 Codex 登录 |
| MiniMax | Coding Plan 5 小时和周限额 | API Key 或 cc-switch |
| OpenAI API | 组织级消费金额 | Admin API Key |
| DeepSeek | 余额 | API Key 或 cc-switch |
| Kimi / Moonshot | 余额 | API Key |
| GLM / 智谱 | 余额 | API Key |
| 小米 MiMo | 在存在可用接口时显示余额 | API Key |
| Claude API | 配置组织级接口后显示消费金额 | Admin API Key |

没有可用凭据的厂商不会显示。所有数值统一为 used / total。余额类圆环
使用配置中的 balanceFull 作为参考总额。

macOS 的厂商设置保存在本机 ~/.rinq/config.json，文件使用受限权限。Rinq
只会将凭据发送到对应的厂商接口。不要提交 ~/.rinq/config.json 或任何 API Key。

## iOS 和 watchOS

Apple 端应用以源码形式提供，运行时不依赖 Mac。iOS 和 watchOS 共享厂商模型
及圆环视图，并包含 iOS 小组件和 watchOS complication。

生成 Xcode 工程并构建模拟器版本：

~~~bash
make ios-build
make watch-build
~~~

如果要安装到实体设备，请在 Xcode 中打开生成的 app/Rinq.xcodeproj，并选择
自己的开发团队。免费 Apple ID 适合本地测试，但需要定期重签；长期安装和
iCloud Keychain 共享需要付费开发者团队。

ChatGPT/Codex 使用非官方接口，仅适用于自行构建或侧载版本。App Store 版本
不应包含这一 collector。

## 配置

macOS daemon 首次运行时会创建 ~/.rinq/config.json。最小配置示例：

~~~json
{
  "collectors": ["codex", "minimax", "deepseek", "openai"],
  "budgetUsd": { "openai": 20.0 },
  "balanceFull": { "deepseek": 100.0 },
  "usage": { "lookbackDays": 7 }
}
~~~

将 `collectors` 设置为 ["mock"] 可以在不请求厂商网络接口的情况下显示模拟数据。
如果 coding agent 把 JSONL 日志放在标准目录之外，可以使用 `usage.extraSources`
添加受支持的本地日志目录。

## 开发

~~~bash
cd mac
python3 -m unittest test_rinq

cd RinqMenu
swift test
swift build -c release
~~~

仓库还包含 iOS/watchOS 源码、厂商适配器、本地 hooks 和公开状态数据契约。
提交代码时请保持凭据只存在于本地，保留明确的离线和错误状态，不要把厂商
密钥写入源码。

## 许可证

Rinq 采用 [Apache License 2.0](LICENSE) 许可证。
