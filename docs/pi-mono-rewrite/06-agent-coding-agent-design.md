# `pi-agent-core` 与 `pi-coding-agent` 设计分析

这份文档把 `packages/agent` 和 `packages/coding-agent` 拆开分析，目的是给后续用 Python 重写提供稳定边界，而不是逐文件照搬实现。

---

## 1. 模块职责

### `pi-agent-core`

[`packages/agent`](../../packages/agent) 是底层 agent 运行时，关注点非常集中：

- 管理 `Agent` 状态机
- 执行 LLM streaming loop
- 管理 tool call 生命周期
- 统一 message / event 协议
- 支持 proxy transport
- 支持 custom message types 通过 declaration merging 扩展

它本质上是一个可复用的“会话编排引擎”，不关心 CLI、session 文件、主题、扩展加载这些产品层能力。

### `pi-coding-agent`

[`packages/coding-agent`](../../packages/coding-agent) 是产品层 CLI。

它在 `pi-ai + pi-agent-core + pi-tui` 之上再加了一层完整应用能力：

- CLI 参数解析与入口分发
- interactive / print / json / rpc 多模式
- session tree、fork、resume、branch、tree navigation
- compaction 和 retry
- settings、auth、model registry
- skills / prompts / themes / extensions
- built-in tools 与 extension tools
- HTML export、package management、config UI

如果说 `pi-agent-core` 是“会说话、会调工具的引擎”，那 `pi-coding-agent` 就是“完整的可配置 coding harness”。

---

## 2. UI / Runtime 架构

### `pi-agent-core` 架构

核心结构是三层：

1. `Agent`
2. `agentLoop` / `agentLoopContinue`
3. `streamFn` / `tool.execute`

运行时的基本流程是：

1. `Agent.prompt()` 或 `Agent.continue()` 接收输入
2. `agent-loop.ts` 组装 `AgentContext` 和 `AgentLoopConfig`
3. `convertToLlm()` 把 `AgentMessage[]` 转成 LLM 可识别的 `Message[]`
4. LLM streaming 返回 assistant delta
5. assistant 消息落地后进入 tool preflight / execution
6. tool 输出再回写为 `toolResult`
7. 进入下一 turn，直到没有更多工具调用

设计重点不是“一个函数跑完”，而是：

- streaming 过程中持续发事件
- assistant / tool / turn 的生命周期都要显式化
- 支持 steering / follow-up 队列
- 允许 proxy transport 替换真实模型调用

### `pi-coding-agent` 架构

`pi-coding-agent` 可以拆成五层：

1. CLI / mode layer
2. session coordinator layer
3. resource / model / settings layer
4. extension layer
5. UI / TUI layer

#### 入口层

`packages/coding-agent/src/main.ts` 负责：

- 参数解析
- package 命令
- config 命令
- migrations
- 运行模式选择
- 资源初始化

`packages/coding-agent/src/cli.ts` 是更轻的编译入口，主要把进程交给 `main()`。

#### 会话编排层

`AgentSession` 是中枢。

它不是单纯包了一层 `Agent`，而是把以下事情编排在一起：

- 订阅 agent 事件
- 持久化 session entry
- 维护 pending steering / follow-up
- 管理 bash execution 回放
- 管理 auto compaction / retry
- 管理 branch / tree / fork / switch
- 给 extension 暴露生命周期钩子

#### 资源层

`DefaultResourceLoader` 负责统一发现和加载：

- extensions
- skills
- prompts
- themes
- `AGENTS.md` / `CLAUDE.md`
- `SYSTEM.md` / `APPEND_SYSTEM.md`

它同时还负责冲突检测、路径 metadata、包资源解析。

#### 扩展层

`ExtensionRunner` 是运行时扩展系统。

它不仅能注册工具、命令、快捷键，还能影响：

- model/provider 请求
- session 创建 / fork / tree / switch / compact
- UI context
- tool flow
- input handling

这说明它的目标不是“插件系统”，而是“让插件能参与整个 agent 生命周期”。

#### UI 层

interactive mode 直接建立在 `pi-tui` 上。

它的职责是：

- 把 `AgentSession` 的事件转成消息组件
- 处理 editor / overlay / selector / loader
- 渲染 header / footer / widgets
- 映射快捷键和输入状态
- 处理 extensions 插入的自定义 UI

---

## 3. 关键接口和消息模型

### `pi-agent-core` 关键接口

#### `AgentState`

核心状态包括：

- `systemPrompt`
- `model`
- `thinkingLevel`
- `tools`
- `messages`
- `isStreaming`
- `streamMessage`
- `pendingToolCalls`
- `error`

#### `AgentTool`

工具接口把 UI 显示和执行统一起来：

- `name`
- `label`
- `description`
- `parameters`
- `execute(toolCallId, params, signal, onUpdate)`

`onUpdate` 支持工具进度流。

#### `AgentEvent`

事件模型明确区分了：

- `agent_start` / `agent_end`
- `turn_start` / `turn_end`
- `message_start` / `message_update` / `message_end`
- `tool_execution_start` / `tool_execution_update` / `tool_execution_end`

这组事件是 UI 和 session 持久化的共同事实来源。

#### `streamFn`

`StreamFn` 是 transport 抽象。

要求是：

- 返回流，不是单次结果
- 失败要编码在流里，而不是简单 reject
- 允许 proxy、SSE、WebSocket、SDK bridge 等不同后端实现

#### custom message types

`AgentMessage` 通过 declaration merging 扩展。

`pi-coding-agent` 里重点扩展了：

- `bashExecution`
- `custom`
- `branchSummary`
- `compactionSummary`

其中 `convertToLlm()` 会把这些自定义消息转成 LLM 能理解的 `user` content，或者在需要时过滤掉。

### `pi-coding-agent` 关键接口

#### `CreateAgentSessionOptions`

创建 session 的关键输入包括：

- `cwd`
- `agentDir`
- `authStorage`
- `modelRegistry`
- `model`
- `thinkingLevel`
- `scopedModels`
- `tools`
- `customTools`
- `resourceLoader`
- `sessionManager`
- `settingsManager`

这意味着 Python 版本也应该把 session 构建做成显式工厂，而不是散落在 CLI 中。

#### `AgentSessionConfig`

`AgentSession` 进一步把：

- `agent`
- `sessionManager`
- `settingsManager`
- `resourceLoader`
- `modelRegistry`
- `customTools`
- `extensionRunnerRef`

绑定到一起。

#### `SessionEntry`

session 文件不是单一消息流，而是 tree 化的 append-only log。

主要 entry 类型有：

- `message`
- `thinking_level_change`
- `model_change`
- `compaction`
- `branch_summary`
- `custom`
- `custom_message`
- `label`
- `session_info`

这是一项重写时必须保留的核心语义。

#### `Settings`

配置是全局和项目两层深度合并。

关键字段包括：

- `defaultProvider`
- `defaultModel`
- `defaultThinkingLevel`
- `transport`
- `steeringMode`
- `followUpMode`
- `theme`
- `compaction`
- `branchSummary`
- `retry`
- `images`
- `enabledModels`
- `treeFilterMode`
- `thinkingBudgets`
- `showHardwareCursor`
- `markdown`

#### `ModelRegistry`

`models.json` 支持：

- provider override
- model override
- custom provider
- custom auth header
- runtime register/unregister provider

这不是静态表，而是一个运行时注册系统。

#### `ExtensionRunner`

扩展运行时要处理的对象很多：

- tools
- commands
- flags
- shortcuts
- UI context
- provider hooks
- lifecycle hooks

它同时会给 extensions 提供：

- session 操作
- tool 列表
- model 切换
- theme 操作
- editor 操作

#### `ResourceLoader`

资源加载层提供的是“发现 + 归一化 + 冲突检查”能力，而不是单纯读目录。

它会产出：

- extensions
- skills
- prompts
- themes
- agents 文件
- system prompt 片段

#### session event 增强事件

`AgentSessionEvent` 在 `AgentEvent` 基础上加了：

- `auto_compaction_start`
- `auto_compaction_end`
- `auto_retry_start`
- `auto_retry_end`

这表示产品层关心的不只是 LLM 输出，还关心编排过程本身。

---

## 4. 运行时依赖

### `pi-agent-core`

`packages/agent/package.json` 体现的是一个很窄的 runtime：

- `@mariozechner/pi-ai`
- `vitest`
- `typescript`
- Node 20+

它核心依赖的是 `pi-ai` 提供的 model / message / transport 能力。

### `pi-coding-agent`

`packages/coding-agent/package.json` 的依赖说明它是一个完整 CLI 应用：

- `@mariozechner/pi-agent-core`
- `@mariozechner/pi-ai`
- `@mariozechner/pi-tui`
- `@mariozechner/jiti`
- `chalk`
- `cli-highlight`
- `diff`
- `extract-zip`
- `file-type`
- `glob`
- `hosted-git-info`
- `ignore`
- `marked`
- `minimatch`
- `proper-lockfile`
- `strip-ansi`
- `undici`
- `yaml`
- `@silvia-odwyer/photon-node`

另外还有两个运行层面的重要点：

- `optionalDependencies` 里的 `@mariozechner/clipboard`
- `build:binary` 里通过 Bun 打包成单文件可执行程序

### 运行时能力映射

从代码看，`pi-coding-agent` 依赖的不是“某个 UI 框架”，而是这些运行时能力：

- 终端输入和光标控制
- JSONL 文件 IO 与 lock
- Git / archive / file type / image processing
- provider auth 和 model discovery
- extension 动态加载
- markdown / code block / diff 渲染

---

## 5. Python 重写路径

这里建议把重写拆成“核心运行时”和“产品外壳”两条线，不要一锅端。

### 5.1 推荐模块拆分

#### `pi_core`

保留：

- `Agent`
- message / tool / event schema
- stream transport
- tool execution
- retry / steering / follow-up

Python 可用：

- `pydantic` 定义消息模型
- `asyncio` 驱动 event stream
- `httpx` / `websockets` / `aiohttp` 做 transport adapter

#### `pi_session`

保留：

- JSONL session log
- tree / fork / branch / label
- compaction / branch summary
- resume / continue

Python 存储可以有两条路：

- 继续用 JSONL，最容易对齐当前设计
- 迁移到 SQLite，但保留 append-only 视图和 tree 索引

如果目标是“先对齐语义”，建议先保留 JSONL。

#### `pi_models`

保留：

- provider registry
- model override
- auth fallback
- dynamic provider register/unregister

Python 实现上建议把 provider 定义成插件式 registry，而不是固定枚举。

#### `pi_resources`

保留：

- skills
- prompts
- themes
- extensions
- AGENTS / SYSTEM 文件
- package source discovery

这里的关键不是文件格式，而是“资源发现 + 合并 + 冲突提示”。

#### `pi_extensions`

保留：

- command / tool / shortcut hooks
- UI hooks
- provider hooks
- session hooks

Python 可以用：

- entry points
- importlib 动态加载
- 约定式插件目录

#### `pi_cli`

保留：

- interactive / print / rpc / json
- package command
- config command
- session picker
- model picker

CLI 层建议用 `Typer` 或 `Click`，因为参数和子命令很多。

### 5.2 UI 方案取舍

#### 终端 UI

如果要重建 `pi-tui` 的能力，推荐优先级是：

1. `Textual` 做主 UI 壳
2. `prompt_toolkit` 做高 fidelity 输入框 / 命令编辑器

取舍：

- `Textual` 适合布局、组件、overlay、消息列表
- `prompt_toolkit` 更适合复杂按键、补全、输入法、粘贴和编辑行为

如果只用 `Textual`，开发会更统一，但编辑器能力大概率比现在弱。

#### Web UI

如果要重建 `web-ui` 级别的能力，不建议纯 `HTMX`。

原因很直接：

- 流式消息很多
- tool / artifact / sandbox 需要双向通信
- attachments 有上传、预览、解析
- artifact 面板需要状态重建

更合适的路线是：

- `FastAPI` + WebSocket / SSE 做后端事件流
- 前端采用轻量 SPA 或组件式前端
- artifact sandbox 用 iframe 或独立隔离页面

如果想快速做一个 MVP，`HTMX` 可以做“聊天 + session 列表 + 简单工具结果”，但不适合完整复刻当前 `web-ui` 的 runtime 复杂度。

### 5.3 建议的迁移顺序

1. 先实现 `Agent` 和 `AgentSession` 的 Python 版核心状态机
2. 再落 `SessionManager` 与 JSONL tree
3. 然后接 `ModelRegistry` / `AuthStorage` / `SettingsManager`
4. 再做 `Textual` TUI
5. 最后再补 web UI、artifact sandbox、attachments、tool renderer registry

### 5.4 最关键的保真点

重写时最不能丢的语义是：

- assistant streaming 事件的细粒度分发
- tool call 的 preflight / execute / postprocess
- session tree 的 append-only 结构
- compaction summary 的可重放性
- extension 对 runtime 的深度介入
- settings / models / resources 的动态热加载

---

## 6. 结论

如果把这两个包合起来看，`pi-mono` 的设计核心其实是：

1. `pi-agent-core` 提供可流式、可扩展、可代理的 agent runtime
2. `pi-coding-agent` 把 runtime 变成一个可配置、可持久化、可扩展的 coding CLI

Python 重写时，最值得优先保留的是“语义边界”，不是“具体 UI 实现”。
只要 session、event、tool、resource、model、extension 这几层语义保住，UI 形态是可以重建的。
