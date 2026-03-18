# Python 重写执行顺序建议

## Phase 1: 基础协议

- 实现 `pi_ai` 的 `Model / Message / Context / Tool / AssistantMessageEvent`
- 实现 stream 抽象
- 实现 provider registry
- 实现最小可用 provider：OpenAI Completions、OpenAI Responses、Anthropic

## Phase 2: Agent runtime

- 实现 `pi_agent_core.Agent`
- 实现 `agent loop`
- 实现 tool execution / validation
- 实现 steering / follow-up 队列
- 实现 proxy transport

## Phase 3: Coding agent

- 实现 session manager
- 实现 settings manager
- 实现 model resolver
- 实现 resource loader
- 实现 CLI main

## Phase 4: 兼容与增强

- cross-provider replay
- compaction
- branch / tree navigation
- extension system
- package system

## 迁移风险

- 流式事件协议如果不严格，UI 会坏
- thinking / reasoning 兼容如果做弱，会破坏多 provider 续跑
- session 树如果不是 append-only，很难复现原行为
- tool result 图片支持不能省
