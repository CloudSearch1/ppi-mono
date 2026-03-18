# `pimono.ai` 可执行代码骨架

这份文档把 `pimono.ai` 的协议草案进一步落成“可以直接开文件写”的 Python 骨架。

目标很明确：

- 先把类型与模块边界固定
- 再把 provider 适配器塞进来
- 最后才考虑高级兼容逻辑

## 1. 建议目录

```text
src/pimono/ai/
├── __init__.py
├── models.py
├── messages.py
├── types.py
├── events.py
├── stream.py
├── registry.py
├── validation.py
├── replay.py
├── api_keys.py
├── transport/
│   ├── __init__.py
│   ├── http.py
│   ├── sse.py
│   └── auth.py
└── providers/
    ├── __init__.py
    ├── anthropic.py
    ├── openai_completions.py
    └── openai_responses.py
```

## 2. 文件职责

### `models.py`

只放模型元信息和成本结构。

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

### `messages.py`

只放消息和 content block。

```python
from dataclasses import dataclass, field
from typing import Any, TypeAlias


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


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    strict: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UserMessage:
    role: str = "user"
    content: str | list[dict[str, Any]] = ""
    timestamp: int | None = None
    attachments: list[Any] = field(default_factory=list)


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


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage
```

### `events.py`

只放流式事件和 usage。

```python
from dataclasses import dataclass
from enum import StrEnum


class AssistantMessageEventType(StrEnum):
    START = "start"
    TEXT_DELTA = "text"
    THINKING_DELTA = "thinking"
    TOOL_CALL_DELTA = "toolcall"
    END = "end"
    DONE = "done"
    ERROR = "error"


@dataclass(slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_input_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class AssistantMessageEvent:
    type: AssistantMessageEventType
    message: "AssistantMessage | None" = None
    text_delta: str | None = None
    thinking_delta: str | None = None
    tool_call_delta: "ToolCallBlock | None" = None
    error: str | None = None
    usage: Usage | None = None
```

### `stream.py`

只放流容器，不放 provider 逻辑。

```python
from collections.abc import AsyncIterator
from typing import Protocol


class AssistantMessageStream(Protocol):
    def __aiter__(self) -> AsyncIterator["AssistantMessageEvent"]: ...
    async def result(self) -> "AssistantMessage": ...
    async def cancel(self) -> None: ...


class EventStreamResult:
    def __init__(self) -> None:
        self._events: list["AssistantMessageEvent"] = []
        self._result: "AssistantMessage | None" = None
```

### `registry.py`

只放 provider registry。

```python
from collections.abc import Callable
from typing import Protocol


class Provider(Protocol):
    api: str

    async def stream(self, model: "Model", context: "Context", options: "StreamOptions") -> "AssistantMessageStream": ...
    async def complete(self, model: "Model", context: "Context", options: "StreamOptions") -> "AssistantMessage": ...


class ApiRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, api_name: str, provider: Provider) -> None:
        ...

    def get(self, api_name: str) -> Provider:
        ...

    def has(self, api_name: str) -> bool:
        return api_name in self._providers
```

### `validation.py`

只放工具参数校验。

```python
from typing import Protocol


class ToolValidator(Protocol):
    def validate(self, tool: "Tool", args: dict[str, object]) -> list[str]: ...
```

### `replay.py`

只放消息重放与 provider 兼容转换。

```python
from typing import Protocol


class MessageReplayer(Protocol):
    def normalize_for_provider(self, messages: list["Message"], target_provider: str) -> list["Message"]: ...
```

### `api_keys.py`

只放环境变量和 OAuth token fallback。

```python
from typing import Protocol


class ApiKeyResolver(Protocol):
    async def get_api_key(self, provider: str) -> str | None: ...
```

## 3. `__init__.py` 导出建议

`pimono.ai.__init__` 应该只导出稳定 API：

```python
from .models import CostProfile, Model
from .messages import AssistantMessage, Message, Tool, ToolResultMessage, UserMessage
from .events import AssistantMessageEvent, AssistantMessageEventType, Usage
from .stream import AssistantMessageStream
from .registry import ApiRegistry, Provider
```

不要把 provider 实现、重放内部工具、transport helper 全部暴露到根包。

## 4. 首批 provider 文件骨架

### `providers/openai_completions.py`

职责：

- 请求 payload 转换
- SSE 事件解析
- tool call 增量拼装
- usage 归集

### `providers/openai_responses.py`

职责：

- responses API payload 转换
- reasoning / thinking block 处理
- tool call / tool result 转换

### `providers/anthropic.py`

职责：

- anthropic messages payload 转换
- thinking block / redacted thinking 处理
- tool use / tool result 处理

## 5. 最小实现顺序

建议按这个顺序实现：

1. `models.py`
2. `messages.py`
3. `events.py`
4. `stream.py`
5. `registry.py`
6. `validation.py`
7. `replay.py`
8. `providers/`

这样可以先把静态协议和流协议稳定下来，再补 provider 细节。

## 6. 兼容点提醒

第一版就要考虑这些事情：

- `AssistantMessage` 不能只有文本
- `toolCall` 的 arguments 可能是半成品 JSON
- provider 错误要能落到 stream 事件里
- `result()` 必须和异步迭代共享同一份最终结果
- `reasoning` / `thinking` 的字段最好从一开始就保留

