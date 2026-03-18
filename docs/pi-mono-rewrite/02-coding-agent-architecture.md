# `pi-coding-agent` 架构分析

## 1. 模块定位

`pi-coding-agent` 是产品层 CLI，基于 `pi-ai + pi-agent-core + pi-tui`，向上提供：

- 交互式编码代理
- session 持久化
- 主题和快捷键
- skills / prompts / extensions
- 包管理
- RPC / print / interactive 三种运行模式

关键入口：

- [`packages/coding-agent/src/main.ts`](../../packages/coding-agent/src/main.ts)
- [`packages/coding-agent/src/core/index.ts`](../../packages/coding-agent/src/core/index.ts)
- [`packages/coding-agent/src/core/sdk.ts`](../../packages/coding-agent/src/core/sdk.ts)
- [`packages/coding-agent/src/core/session-manager.ts`](../../packages/coding-agent/src/core/session-manager.ts)
- [`packages/coding-agent/src/core/settings-manager.ts`](../../packages/coding-agent/src/core/settings-manager.ts)
- [`packages/coding-agent/src/core/model-resolver.ts`](../../packages/coding-agent/src/core/model-resolver.ts)

## 2. 运行时分层

### CLI 层

`main.ts` 负责：

- 解析参数
- 处理 package 命令
- 处理 config 命令
- 初始化 migrations
- 初始化 extensions / resource loader
- 构造 session
- 根据模式进入 interactive / print / rpc

### SDK 层

`sdk.ts` 负责把：

- `AuthStorage`
- `ModelRegistry`
- `SessionManager`
- `SettingsManager`
- `ResourceLoader`
- built-in tools

组合成一个 `AgentSession`。

### 状态存储层

`SessionManager` 使用 JSONL 树结构管理会话历史，支持：

- append-only
- branch
- fork
- resume
- compaction
- label

`SettingsManager` 管理 global/project 两层配置，并做深度合并。

## 3. 关键设计点

### 模型解析

`model-resolver.ts` 负责：

- model pattern 解析
- provider/model 解耦
- glob scope
- thinking level 解析
- 默认模型 fallback

### 资源加载

`DefaultResourceLoader` 负责发现：

- extensions
- skills
- prompts
- themes

并提供给 CLI 和 session 初始化。

### AgentSession

`AgentSession` 是 coding-agent 的核心业务对象，负责把：

- agent runtime
- tools
- session manager
- settings manager
- extensions

结合起来。

## 4. Python 重写建议

建议把 coding-agent 拆成：

- `pi_cli/`：命令行、参数、运行模式
- `pi_session/`：session tree、fork/branch/compaction
- `pi_resources/`：skills/prompts/extensions/themes
- `pi_runtime/`：AgentSession 的业务编排

需要特别保留的语义：

- session JSONL 的树结构
- `continue/resume/fork/tree` 的行为
- 资源热加载
- extensions 对 CLI flag 和 provider registration 的注入能力
- settings 的 global/project 合并

