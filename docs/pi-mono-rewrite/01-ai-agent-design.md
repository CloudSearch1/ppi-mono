# `pi-ai` 与 `pi-agent-core` 设计分析

## 1. 模块职责与边界

### `pi-ai`

`pi-ai` 是统一 LLM 接入层，负责：

- 模型与 provider 注册
- 环境变量和 OAuth 鉴权解析
- 把统一 `Context` 转成各家 API payload
- 把 provider 流式响应转成统一事件协议
- 计算 token 和费用
- 跨 provider 消息重放和兼容转换

它不负责：

- agent 状态机
- 工具执行
- session / UI / CLI

关键入口：

- [`packages/ai/src/index.ts`](../../packages/ai/src/index.ts)
- [`packages/ai/src/stream.ts`](../../packages/ai/src/stream.ts)
- [`packages/ai/src/types.ts`](../../packages/ai/src/types.ts#L190)
- [`packages/ai/src/api-registry.ts`](../../packages/ai/src/api-registry.ts#L66)

### `pi-agent-core`

`pi-agent-core` 是 agent 编排层，负责：

- 维护 `AgentState`
- 执行 agent loop
- 调度 tool execution
- 管理 steering / follow-up 队列
- 提供事件订阅接口
- 适配 proxy transport

它不负责：

- provider 细节
- 具体 UI
- session 持久化

关键入口：

- [`packages/agent/src/agent.ts`](../../packages/agent/src/agent.ts#L116)
- [`packages/agent/src/agent-loop.ts`](../../packages/agent/src/agent-loop.ts#L31)
- [`packages/agent/src/types.ts`](../../packages/agent/src/types.ts)
- [`packages/agent/src/proxy.ts`](../../packages/agent/src/proxy.ts)

## 2. 核心数据结构

### `pi-ai`

- `Model<TApi>`: 模型元数据，包含 provider、api、baseUrl、reasoning、cost、contextWindow、maxTokens、compat。
- `Context`: `{ systemPrompt, messages, tools }`
- `Message`: `user | assistant | toolResult`
- `AssistantMessage`: 统一输出结构，content 为 `text | thinking | toolCall`
- `ToolCall`: 统一 tool 调用块，包含 `id/name/arguments`
- `AssistantMessageEvent`: 流式协议，必须严格遵守 `start/delta/end/done/error`
- `StreamOptions` / `SimpleStreamOptions`: 统一请求参数

### `pi-agent-core`

- `AgentMessage`: 可扩展消息联合类型
- `AgentTool`: 带执行函数的工具定义
- `AgentState`: 当前会话状态
- `AgentLoopConfig`: loop 运行时依赖注入
- `AgentEvent`: 面向 UI / 日志 / 上层应用的事件

## 3. 关键运行流程

### `pi-ai`

1. `stream(model, context, options)` 通过 [`api-registry.ts`](../../packages/ai/src/api-registry.ts#L66) 找到 provider。
2. provider 把统一 `Context` 转成 API payload。
3. provider 发出请求并解析流式响应。
4. provider 实时构造 `AssistantMessageEventStream`。
5. `complete()` 只是 `stream().result()`。

### `pi-agent-core`

1. `Agent.prompt()` 或 `Agent.continue()` 进入 `_runLoop()`。
2. 组装 `AgentContext` 和 `AgentLoopConfig`。
3. `runAgentLoop()` 触发 `agent_start` / `turn_start`。
4. `streamAssistantResponse()` 调 `streamSimple()`。
5. assistant 消息结束后，执行 tool preflight、tool execution、after hook。
6. 根据 steering / follow-up 决定是否继续 turn。
7. 最终 emit `agent_end`。

## 4. 兼容性约束

以下语义在 Python 重写中必须保留：

- partial tool JSON 增量解析
- thinking block 和 redacted thinking 的回放
- tool call id 归一化
- aborted/error 也要作为最终 assistant 消息返回
- toolResult 可携带图片
- parallel tool execution 的顺序语义
- `sessionId` / `cacheRetention` / `onPayload` / `transport`

## 5. Python 重写建议

### 推荐拆分

- `pi_ai/`
- `pi_agent_core/`

### `pi_ai` 建议接口

- `Model`, `Message`, `Context`, `Tool`, `Usage` 使用 dataclass 或 pydantic
- `Provider` 用协议类抽象
- `AssistantMessageStream` 用 async iterator 表达事件流
- 统一保留 `result()` 方法

### `pi_agent_core` 建议接口

- `Agent` 负责状态机
- `AgentTool.execute()` 支持异步 + progress callback
- `AgentLoopConfig` 通过依赖注入提供可替换逻辑
- `AgentEvent` 作为唯一事件出口

### 建议额外保留

- `beforeToolCall` / `afterToolCall`
- steering / follow-up 队列
- transport 插件
- 对 provider 级别鉴权的动态解析

