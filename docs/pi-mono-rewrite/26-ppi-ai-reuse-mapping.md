# `ppi_ai` 复用映射与新包边界

这份文档把 `mom` / `pods` 继续映射到现有的 `python/src/ppi_ai`，明确哪些能力可以直接复用，哪些应该留在 `ppi_mom` / `ppi_pods` / `ppi_coding_agent`。

---

## 1. 可以直接复用的 `ppi_ai`

`ppi_ai` 已经很适合做 Python 重写的协议内核，以下内容可以直接复用：

- `python/src/ppi_ai/models.py`
  - `Model`
  - `Context`
  - `Message`
  - `UserMessage`
  - `AssistantMessage`
  - `ToolResultMessage`
  - `ToolCall`
  - `Tool`
  - `StreamOptions`
  - `SimpleStreamOptions`
  - `Usage`
- `python/src/ppi_ai/events.py`
  - `AssistantMessageEvent`
  - `StreamStartEvent`
  - `TextDeltaEvent`
  - `ThinkingDeltaEvent`
  - `ToolCallStartEvent`
  - `StreamDoneEvent`
  - `StreamErrorEvent`
- `python/src/ppi_ai/auth.py`
  - `ApiKeySource`
  - `EnvironmentApiKeySource`
  - `OAuthCredential`
- `python/src/ppi_ai/registry.py`
  - `Provider`
  - `AssistantMessageStream`
  - `ProviderRegistry`
  - `ApiRegistry`
- `python/src/ppi_ai/stream.py`
  - `stream()`
  - `complete()`

这些模块已经覆盖了模型协议、流式事件、provider registry 和基础认证来源。

---

## 2. `mom` 对 `ppi_ai` 的复用方式

`mom` 不应该重新定义 LLM 消息模型，而应该直接复用 `ppi_ai`：

- `Slack` 消息进入后，转换成 `ppi_ai.models.UserMessage`
- `agent run` 返回的内容，转换成 `ppi_ai.models.AssistantMessage`
- tool 执行结果，转换成 `ppi_ai.models.ToolResultMessage`
- session sync 时，直接把历史消息重建为 `ppi_ai.models.Context`

也就是说：

```text
ppi_mom
  -> 负责 Slack / log / attachments / scheduler / sandbox
  -> 复用 ppi_ai 的消息协议与流式协议
```

---

## 3. `pods` 对 `ppi_ai` 的复用方式

`pods` 主要复用的是模型和 provider 协议，而不是 Slack 语义：

- `Model`：用于描述远端 vLLM 暴露出来的 OpenAI-compatible endpoint
- `Provider` / `ProviderRegistry`：用于把远端模型纳入统一 provider 路由
- `ApiKeySource`：用于读取 `PI_API_KEY` 或环境变量中的 key
- `AssistantMessageEvent`：用于把 agent CLI 的流式输出统一到同一协议

`pods` 不应把 SSH / pod config / process management 混进 `ppi_ai`。

---

## 4. 应该新建的包

以下能力应该保留在专门的新包里，而不是塞回 `ppi_ai`：

- `ppi_mom`
  - Slack adapter
  - workspace store
  - attachment downloader
  - scheduler watcher
  - sandbox executor
- `ppi_pods`
  - pod config store
  - SSH/SCP executor
  - model planner
  - vLLM runtime controller
  - CLI commands
- `ppi_coding_agent`
  - session manager
  - settings manager
  - resource loader
  - extension system

这些都是“应用编排层”能力，不属于 LLM 协议层。

---

## 5. 建议的依赖方向

```text
ppi_ai
  ↑
ppi_coding_agent
  ↑
ppi_mom
ppi_pods
```

解释如下：

- `ppi_ai` 提供最底层协议
- `ppi_coding_agent` 负责 session / settings / resource / extension
- `ppi_mom` 和 `ppi_pods` 作为应用入口，复用上层协议

---

## 6. 现有骨架与新骨架的对应

当前 `python/src` 里的骨架已经有这些包：

- `ppi_ai`
- `ppi_coding_agent`
- `ppi_mom`
- `ppi_pods`
- `ppi_tui`
- `ppi_web`

这次新增的文件主要是把 `ppi_mom` / `ppi_pods` 进一步拆成：

- `protocols.py`
- `runtime.py`
- 命令级 `.py` 骨架

这样它们就能更明确地对接 `ppi_ai`。

