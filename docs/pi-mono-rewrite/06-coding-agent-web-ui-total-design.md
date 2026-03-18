# `pi-coding-agent` + `pi-web-ui` 总体设计

这份文档把产品层 `pi-coding-agent` 和浏览器层 `pi-web-ui` 合并为一套 Python 重写目标，重点描述它们如何围绕 `AgentSession`、session 存储、资源发现和消息渲染协作。

## 1. 职责边界

### `pi-coding-agent`

它是产品级 CLI 和会话运行时，负责：

- 交互式、print、RPC 三种运行模式
- session 树和持久化
- 资源发现：skills、prompts、themes、extensions、AGENTS.md
- 模型解析、鉴权解析、默认模型选择
- extension 生命周期
- compaction、fork、branch、tree navigation
- built-in tool 编排

### `pi-web-ui`

它是浏览器侧聊天与 artifact 运行时，负责：

- ChatPanel 布局
- AgentInterface 消息流渲染
- attachments 解析与预览
- IndexedDB 存储
- artifact 面板与 sandbox iframe
- tool renderer registry
- custom message 类型和 LLM 转换

### 边界原则

- `coding-agent` 管 session 和 agent 生命周期
- `web-ui` 管 UI 和浏览器存储
- 两者共享的核心协议应来自 `pi-ai` / `pi-agent-core`

## 2. 架构分层

### 产品层

```text
CLI / Browser App
  -> AgentSession
  -> SessionManager / SettingsManager / ResourceLoader / ModelRegistry
  -> Agent
  -> pi-ai providers
```

### `pi-coding-agent` 内部分层

- `src/main.ts`
  - CLI 入口与模式切换
- `src/core/sdk.ts`
  - 组装 session runtime
- `src/core/agent-session.ts`
  - 业务中枢
- `src/core/session-manager.ts`
  - append-only session tree
- `src/core/settings-manager.ts`
  - global/project settings
- `src/core/model-registry.ts`
  - 模型与 API key 解析
- `src/core/resource-loader.ts`
  - extensions / skills / prompts / themes / context files
- `src/core/extensions/*`
  - extension runtime、loader、wrapper、event bus

### `pi-web-ui` 内部分层

- `ChatPanel`
  - 总布局
- `AgentInterface`
  - 消息列表、输入框、状态、发送逻辑
- `MessageList` / `StreamingMessageContainer`
  - 稳定消息与流式消息分离
- `storage/*`
  - IndexedDB 抽象
- `tools/*`
  - artifact/tool 渲染与执行
- `components/sandbox/*`
  - iframe bridge 与 runtime provider

## 3. 关键接口定义

### `AgentSession`

建议 Python 版保留以下方法语义：

- `prompt(input, options) -> await`
- `continue() -> await`
- `abort()`
- `setModel(model)`
- `setThinkingLevel(level)`
- `setTools(tools)`
- `setSystemPrompt(text)`
- `switchSession(path)`
- `fork(entry_id)`
- `navigateTree(entry_id, summarize=...)`
- `exportToHtml()`
- `getSessionStats()`

### `SessionManager`

核心模型：

- session 是 append-only JSONL tree
- 每条 entry 具有 `id`、`parentId`、`timestamp`
- leaf pointer 决定当前分支

关键 entry 类型：

- `message`
- `thinking_level_change`
- `model_change`
- `compaction`
- `branch_summary`
- `custom`
- `custom_message`
- `label`
- `session_info`

### `SettingsManager`

建议 Python 版保留双层 settings：

- global scope
- project scope

关键设置类：

- `defaultProvider`
- `defaultModel`
- `defaultThinkingLevel`
- `transport`
- `steeringMode`
- `followUpMode`
- `compaction`
- `retry`
- `terminal`
- `images`
- `packages`
- `extensions`
- `skills`
- `prompts`
- `themes`

### `ResourceLoader`

返回值应包含：

- extensions
- skills
- prompts
- themes
- agents files
- system prompt
- append system prompt
- path metadata

`reload()` 必须支持热重载和路径冲突检测。

### `web-ui` storage

建议保留以下抽象：

- `StorageBackend`
- `StorageTransaction`
- `SessionsStore`
- `ProviderKeysStore`
- `SettingsStore`
- `CustomProvidersStore`

session 数据建议分成：

- full session
- session metadata

### `web-ui` message types

关键扩展消息：

- `user-with-attachments`
- `artifact`

转换器职责：

- `defaultConvertToLlm(messages)`
- `convertAttachments(attachments)`

## 4. 运行时流程

### `pi-coding-agent` 启动

1. CLI 解析参数。
2. 初始化 settings / resources / model registry。
3. 创建 `AgentSession`。
4. 加载 session 树与 resources。
5. 进入 interactive / print / rpc 模式。

### `AgentSession.prompt()`

1. 构建用户消息。
2. 处理 prompt template、skills、images。
3. 调用 `Agent.prompt()`。
4. 监听 agent 事件并持久化。
5. 执行 compaction / retry / tool hooks。
6. 更新 session tree 与 UI 状态。

### `web-ui` message send

1. `AgentInterface.sendMessage()` 校验 session 和 API key。
2. 如有附件，生成 `user-with-attachments`。
3. 调 `session.prompt()`。
4. 监听 `message_start/message_update/message_end`。
5. 更新 stable list 和 streaming container。

### `web-ui` artifact flow

1. `ArtifactsPanel` 作为 tool 接收 LLM 输出。
2. 解析 artifact 消息并写入内部状态。
3. 通过 runtime provider 暴露给 sandbox iframe。
4. 允许浏览器中的 JS 读取 / 写入 artifact。

## 5. Python 重写建议

### 推荐模块

- `ppi.runtime`
  - `AgentSession`
  - CLI / RPC / print mode
- `ppi.session`
  - session tree
  - compaction
  - branch / fork / tree
- `ppi.resources`
  - extension / skill / prompt / theme discovery
- `ppi.settings`
  - layered settings backend
- `ppi.web`
  - web UI state
  - attachments
  - artifacts
  - storage

### 需要保留的语义

- session tree append-only
- branch 和 fork 不是简单复制，而是保留父子关系
- compaction 结果要进入历史
- extension 可以影响 tool/command/flags/context
- web 侧要分离稳定消息与流式消息

### 可以简化的部分

- TUI / web 的底层渲染库可以替换
- 包管理实现可先收敛到最基本路径
- 资源发现的路径兼容可以逐步补齐

## 6. 风险

- 如果 session tree 不保留 append-only 语义，fork/tree/compaction 都会变脆弱。
- 如果 resource loader 不做冲突检测，extension 之间会互相覆盖。
- 如果 web storage 不分 metadata/full-session，列表性能会快速下降。
- 如果流式消息和稳定消息没有分离，浏览器渲染会抖动。

