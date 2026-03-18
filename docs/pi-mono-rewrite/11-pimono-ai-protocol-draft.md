# `pimono.ai` 第一版协议草案

这份草案只定义 `pimono.ai` 的基础协议层，不涉及 agent loop、session、UI 或业务编排。

目标是让 Python 版的 LLM 接口具备和 `pi-ai` 类似的稳定边界：

- 统一消息模型
- 统一流式事件模型
- 统一 provider 抽象
- 统一工具 schema
- 统一上下文结构

## 1. 设计原则

### 1.1 以协议为中心

`pimono.ai` 不应该直接绑定某个 provider SDK。

正确做法是：

- 先定义内部协议
- 再为 OpenAI / Anthropic / 其他 provider 写适配器

### 1.2 事件优先于回调

流式 API 的第一等公民应该是事件，而不是回调堆叠。

原因：

- 更容易做 async iterator
- 更容易做日志和回放
- 更容易在 agent 层拼接状态

### 1.3 消息与事件分离

消息描述“最终状态”。
事件描述“状态变化”。

这两者必须分开，否则 streaming、abort、partial tool call、thinking block 都会混到一起。

## 2. 核心数据模型

### 2.1 `Model`

`Model` 描述一个可调用的模型实例。

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class CostProfile:
    input_per_1k_tokens: float | None = None
    output_per_1k_tokens: float | None = None
    cached_input_per_1k_tokens: float | None = None
    reasoning_per_1k_tokens: float | None = None


@dataclass(slots=True)
class Model:
    provider: str
    api: str
    id: str
    base_url: str | None = None
    reasoning: bool = False
    context_window: int | None = None
    max_tokens: int | None = None
    default_temperature: float | None = None
    cost: CostProfile | None = None
    compat: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
```

字段建议：

- `provider`: 逻辑 provider 名称，例如 `anthropic`、`openai`
- `api`: 传给 registry 的接口族名称
- `id`: 具体模型 id
- `base_url`: 自定义 endpoint 时使用
- `reasoning`: 是否启用 reasoning / thinking 能力
- `context_window`: 上下文窗口
- `max_tokens`: 默认输出上限
- `compat`: provider 特有兼容开关

### 2.2 `Context`

```python
@dataclass(slots=True)
class Context:
    system_prompt: str | None
    messages: list["Message"]
    tools: list["Tool"] = field(default_factory=list)
```

`Context` 是 LLM 请求的最小输入壳。

它不应该包含：

- session 树
- UI 状态
- 扩展系统内部状态

### 2.3 `Tool`

工具只描述 schema，不描述执行逻辑。

```python
@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    strict: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 2.4 Message block

建议把 assistant 输出拆成 block，而不是一坨字符串。

```python
@dataclass(slots=True)
class TextBlock:
    type: str = "text"
    text: str = ""


@dataclass(slots=True)
class ThinkingBlock:
    type: str = "thinking"
    text: str = ""
    redacted: bool = False


@dataclass(slots=True)
class ToolCallBlock:
    type: str = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    arguments_raw: str | None = None


@dataclass(slots=True)
class ToolResultBlock:
    type: str = "toolResult"
    tool_call_id: str = ""
    name: str = ""
    content: Any = None
    is_error: bool = False
```

### 2.5 Message

最小消息集建议如下：

```python
@dataclass(slots=True)
class UserMessage:
    role: str = "user"
    content: str | list[dict[str, Any]] = ""
    timestamp: int | None = None
    attachments: list["Attachment"] = field(default_factory=list)


@dataclass(slots=True)
class AssistantMessage:
    role: str = "assistant"
    content: list[TextBlock | ThinkingBlock | ToolCallBlock] = field(default_factory=list)
    usage: "Usage | None" = None
    stop_reason: str | None = None
    error_message: str | None = None
    response_id: str | None = None
    timestamp: int | None = None


@dataclass(slots=True)
class ToolResultMessage:
    role: str = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: Any = None
    is_error: bool = False
    timestamp: int | None = None
```

建议 `Message` 用 `typing.Union` 或 `typing.TypeAlias` 定义：

```python
Message = UserMessage | AssistantMessage | ToolResultMessage
```

## 3. 流式事件

### 3.1 事件枚举

```python
from enum import StrEnum

class AssistantMessageEventType(StrEnum):
    START = "start"
    TEXT_DELTA = "text"
    THINKING_DELTA = "thinking"
    TOOL_CALL_DELTA = "toolcall"
    END = "end"
    DONE = "done"
    ERROR = "error"
```

### 3.2 事件模型

```python
@dataclass(slots=True)
class AssistantMessageEvent:
    type: AssistantMessageEventType
    message: AssistantMessage | None = None
    text_delta: str | None = None
    thinking_delta: str | None = None
    tool_call_delta: ToolCallBlock | None = None
    error: str | None = None
    usage: "Usage | None" = None
```

### 3.3 流容器

```python
class AssistantMessageStream(Protocol):
    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]: ...
    async def result(self) -> AssistantMessage: ...
    async def cancel(self) -> None: ...
```

行为要求：

- `start` 事件必须先出现
- `done` / `error` 必须终结流
- `result()` 必须返回最终 assistant message
- `cancel()` 不能破坏已生成的部分结果

## 4. Usage 与 token 统计

```python
@dataclass(slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None
    total_tokens: int | None = None
```

建议保留 reasoning token 字段，因为现有实现把 reasoning/thinking 当成重要兼容面。

## 5. Options

### 5.1 `StreamOptions`

```python
@dataclass(slots=True)
class StreamOptions:
    temperature: float | None = None
    max_tokens: int | None = None
    api_key: str | None = None
    session_id: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    on_payload: Callable[[dict[str, Any]], None] | None = None
    transport: "Transport | None" = None
    cache_retention: bool | None = None
```

### 5.2 `SimpleStreamOptions`

```python
@dataclass(slots=True)
class SimpleStreamOptions(StreamOptions):
    pass
```

后续如果发现 `simple` 和 `full` 差异变大，再拆分独立类型。

## 6. Provider 协议

### 6.1 `Provider`

```python
class Provider(Protocol):
    api: str

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessageStream: ...

    async def complete(
        self,
        model: Model,
        context: Context,
        options: StreamOptions,
    ) -> AssistantMessage: ...
```

### 6.2 `SimpleProvider`

如果后面要保留 `streamSimple()` / `completeSimple()` 语义，可以额外定义：

```python
class SimpleProvider(Protocol):
    async def stream_simple(self, model: Model, context: Context, options: SimpleStreamOptions) -> AssistantMessageStream: ...
    async def complete_simple(self, model: Model, context: Context, options: SimpleStreamOptions) -> AssistantMessage: ...
```

但建议优先把 `stream()` / `complete()` 做稳，再用适配器层提供 simple 入口。

## 7. Registry

### 7.1 `ApiRegistry`

```python
class ApiRegistry(Protocol):
    def register(self, api_name: str, provider: Provider) -> None: ...
    def get(self, api_name: str) -> Provider: ...
    def has(self, api_name: str) -> bool: ...
    def list(self) -> list[str]: ...
    def clear(self) -> None: ...
```

### 7.2 注册约束

- 同名 API 不应该无声覆盖
- builtin provider 和 custom provider 应分层注册
- registry 应能按环境动态构建

## 8. Replay 与 message normalization

`pimono.ai` 需要一个独立的 replay / normalization 层，处理：

- thinking block 重放
- redacted thinking 兼容
- tool call id 归一化
- orphan tool result / tool call 补偿
- provider 间消息降级

建议接口：

```python
class MessageReplayer(Protocol):
    def normalize_for_provider(self, messages: list[Message], target_provider: str) -> list[Message]: ...
```

这层不要放进 provider 本身，否则 provider 会越来越臃肿。

## 9. 校验与错误模型

### 9.1 工具校验

建议使用 `jsonschema` 或 `pydantic` 做工具参数校验。

接口建议：

```python
class ToolValidator(Protocol):
    def validate(self, tool: Tool, args: dict[str, Any]) -> list[str]: ...
```

### 9.2 错误模型

建议让 provider 层和 stream 层都使用统一错误结构。

```python
@dataclass(slots=True)
class ProviderError(Exception):
    message: str
    code: str | None = None
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)
```

## 10. 第一版落地建议

第一版建议只做这些：

- `Model`
- `Context`
- `Tool`
- `AssistantMessage`
- `AssistantMessageEvent`
- `Usage`
- `StreamOptions`
- `Provider`
- `AssistantMessageStream`
- `ApiRegistry`

等这批类型稳定后，再补：

- replay
- validation
- provider-specific compat
- transport abstraction

## 11. 与 TypeScript 版的兼容提醒

要特别注意这些行为不要丢：

- `AssistantMessage` 的内容不是纯文本
- thinking block 可能被 redacted
- tool call arguments 可能是增量 JSON
- provider 错误会以流事件形式返回
- usage / stop reason / response id 不能省
- 多 provider 回放时消息必须可降级

