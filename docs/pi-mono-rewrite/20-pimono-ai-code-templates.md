# `ppi_ai` 文件级 Python 代码模板

这份文档把 `pimono.ai` 进一步拆成可直接对照实现的代码文件模板。

它的目的不是替换现有源码，而是给 `python/src/ppi_ai/` 里的文件一个稳定的“应该长什么样”的参考。

## 1. 当前目标

`ppi_ai` 应该形成下面这组稳定文件：

```text
python/src/ppi_ai/
├── __init__.py
├── auth.py
├── events.py
├── models.py
├── registry.py
├── stream.py
├── providers/
│   ├── __init__.py
│   └── base.py
```

如果后续再补 provider 实现，可以继续加：

```text
├── providers/
│   ├── anthropic.py
│   ├── openai_completions.py
│   └── openai_responses.py
```

## 2. `__init__.py`

根包只导出稳定 API，不暴露实现细节。

```python
"""LLM protocol layer for the Python rewrite."""

from .auth import ApiKeySource, OAuthCredential, OAuthProvider
from .events import AssistantMessageEvent, StreamDoneEvent, StreamErrorEvent
from .models import (
    AssistantMessage,
    Context,
    ImageContent,
    Message,
    Model,
    SimpleStreamOptions,
    StreamOptions,
    ThinkingContent,
    ThinkingLevel,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from .registry import ApiRegistry, Provider, ProviderRegistry, get_provider, register_provider
from .stream import AssistantMessageStream, complete, stream

__all__ = [...]
```

### 建议

- 只导出最稳定的类型
- provider 实现留在 `providers/`
- 事件和模型用 `__all__` 控制 API 面

## 3. `models.py`

`models.py` 是协议层核心。它应该只包含：

- message content blocks
- `Model`
- `Context`
- `Tool`
- `Usage`
- `StreamOptions`
- `SimpleStreamOptions`
- provider compat 结构

### 推荐结构

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

ThinkingLevel: TypeAlias = Literal["minimal", "low", "medium", "high", "xhigh"]
CacheRetention: TypeAlias = Literal["none", "short", "long"]
Transport: TypeAlias = Literal["sse", "websocket", "auto"]
StopReason: TypeAlias = Literal["stop", "length", "toolUse", "error", "aborted"]


@dataclass(slots=True)
class TextContent: ...


@dataclass(slots=True)
class ThinkingContent: ...


@dataclass(slots=True)
class ImageContent: ...


@dataclass(slots=True)
class ToolCall: ...


@dataclass(slots=True)
class Usage: ...


@dataclass(slots=True)
class UserMessage: ...


@dataclass(slots=True)
class AssistantMessage: ...


@dataclass(slots=True)
class ToolResultMessage: ...


Message: TypeAlias = UserMessage | AssistantMessage | ToolResultMessage


@dataclass(slots=True)
class Tool: ...


@dataclass(slots=True)
class Context: ...


@dataclass(slots=True)
class StreamOptions: ...


@dataclass(slots=True)
class SimpleStreamOptions(StreamOptions): ...
```

### 关键兼容点

- assistant content 不是单一字符串
- tool call arguments 要支持增量拼装
- usage / stop_reason / response_id 不能省
- image content 不能被过滤掉

## 4. `events.py`

`events.py` 只定义流式协议，不定义 provider 逻辑。

### 推荐结构

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from .models import AssistantMessage, ToolCall


@dataclass(slots=True)
class StreamStartEvent: ...


@dataclass(slots=True)
class TextStartEvent: ...


@dataclass(slots=True)
class TextDeltaEvent: ...


@dataclass(slots=True)
class TextEndEvent: ...


@dataclass(slots=True)
class ThinkingStartEvent: ...


@dataclass(slots=True)
class ThinkingDeltaEvent: ...


@dataclass(slots=True)
class ThinkingEndEvent: ...


@dataclass(slots=True)
class ToolCallStartEvent: ...


@dataclass(slots=True)
class ToolCallDeltaEvent: ...


@dataclass(slots=True)
class ToolCallEndEvent: ...


@dataclass(slots=True)
class StreamDoneEvent: ...


@dataclass(slots=True)
class StreamErrorEvent: ...


AssistantMessageEvent: TypeAlias = (
    StreamStartEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
    | StreamDoneEvent
    | StreamErrorEvent
)
```

### 关键要求

- start / delta / end / done / error 的顺序要稳定
- event 对象要带 `partial` 或 `message` 快照，方便上层 UI 直接消费

## 5. `registry.py`

`registry.py` 是 provider 路由中心。

### 推荐结构

```python
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from .events import AssistantMessageEvent
from .models import AssistantMessage, Context, Model, StreamOptions


class AssistantMessageStream(Protocol): ...


class Provider(Protocol):
    name: str
    api: str

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessageStream: ...

    async def complete(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessage: ...


@dataclass(slots=True)
class ProviderRegistry:
    providers: dict[str, Provider] = field(default_factory=dict)

    def register(self, name: str, provider: Provider) -> None: ...
    def get(self, name: str) -> Provider: ...


ApiRegistry = ProviderRegistry
```

### 关键要求

- registry 不要在 import 时自动注册 provider
- custom provider 和 builtin provider 的覆盖关系要明确
- `get()` 失败时给出明确错误

## 6. `stream.py`

`stream.py` 只做高层 helper。

### 推荐结构

```python
from __future__ import annotations

from .models import AssistantMessage, Context, Model, SimpleStreamOptions
from .registry import AssistantMessageStream, get_provider


async def stream(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageStream:
    ...


async def complete(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessage:
    ...
```

### 关键要求

- `stream()` 只做 provider lookup + delegation
- `complete()` 只做一次完整请求
- 不要把 provider 细节写进这里

## 7. `auth.py`

`auth.py` 只放鉴权相关协议和数据结构。

### 推荐结构

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeAlias


class ApiKeySource(Protocol):
    def get(self, provider: str) -> str | None: ...


@dataclass(slots=True)
class OAuthCredential:
    provider: str
    token: str
    refresh_token: str | None = None
    expires_at: int | None = None


OAuthProvider: TypeAlias = str
```

### 关键要求

- API key lookup 不能绑死到 env
- OAuth token 和 API key 都应被上层视为“可用凭据”

## 8. `providers/base.py`

这是 provider adapter 的基类模板。

### 推荐结构

```python
from __future__ import annotations

from dataclasses import dataclass

from ..models import AssistantMessage, Context, Model, StreamOptions
from ..registry import AssistantMessageStream, Provider


@dataclass(slots=True)
class BaseProvider(Provider):
    name: str = ""
    api: str = ""

    async def stream(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessageStream:
        raise NotImplementedError

    async def complete(
        self,
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessage:
        raise NotImplementedError
```

### 关键要求

- 基类只定义协议，不实现业务
- 每个 provider 文件只处理自己的 payload 转换和流解析

## 9. 推荐补充的 provider 文件模板

每个 provider 文件都建议遵守同样结构：

```python
"""
Provider adapter for <provider name>.
"""

from __future__ import annotations

from .base import BaseProvider


class <ProviderName>Provider(BaseProvider):
    name = "<provider>"
    api = "<api family>"

    async def stream(...):
        ...

    async def complete(...):
        ...
```

## 10. 和现有实现的对接建议

如果你要从当前 `python/src/ppi_ai` 继续演进，建议保持：

- `models.py` 作为核心协议承载点
- `events.py` 作为事件协议承载点
- `registry.py` 作为 provider 路由承载点
- `stream.py` 作为入口 helper
- `providers/base.py` 作为 provider 模板基类

这样后续补 provider 时，文件边界不会乱。

