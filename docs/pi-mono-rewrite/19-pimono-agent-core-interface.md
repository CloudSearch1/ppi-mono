# `pimono.agent_core` 第一版接口草案

这份文档定义 Python 版 `agent_core` 的最小接口面，不涉及 `coding_agent` 的 session / settings / extensions 细节。

目标是把 agent loop 独立成一个可复用 runtime：

- 输入：`AgentState` + `Context` + `tools`
- 输出：`AgentEvent` 流
- 依赖：`pimono.ai`

## 1. 设计目标

`pimono.agent_core` 要做的事情只有三类：

1. 维护 agent 状态
2. 运行 loop
3. 暴露事件

不要把这些和 session tree、settings merge、extension discovery 混在一起。

## 2. 文件结构

```text
src/pimono/agent_core/
├── __init__.py
├── agent.py
├── state.py
├── tools.py
├── events.py
├── loop.py
├── proxy.py
└── compatibility.py
```

## 3. 状态模型

### `AgentState`

`AgentState` 是 agent runtime 的唯一可变状态容器。

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentState:
    system_prompt: str
    model: "Model"
    thinking_level: str
    tools: list["AgentTool"]
    messages: list["AgentMessage"] = field(default_factory=list)
    is_streaming: bool = False
    stream_message: "AgentMessage | None" = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error: str | None = None
```

### `ThinkingLevel`

建议保留与 TS 相近的等级：

```python
from typing import Literal

ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh"]
```

## 4. Tool 模型

### `AgentTool`

工具是“可执行 schema”。

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


class AbortSignal(Protocol):
    @property
    def aborted(self) -> bool: ...


@dataclass(slots=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[[str, dict[str, Any], AbortSignal | None], Awaitable[Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
```

建议在第一版里就保留异步 `execute`，因为工具会有 shell / IO / network 行为。

## 5. Event 模型

### `AgentEvent`

`AgentEvent` 是 UI、CLI、RPC 的唯一监听出口。

```python
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AgentEventType(StrEnum):
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    MESSAGE_START = "message_start"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_END = "message_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    ERROR = "error"


@dataclass(slots=True)
class AgentEvent:
    type: AgentEventType
    message: "AgentMessage | None" = None
    turn_id: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
```

### Event 约束

- `agent_start` 必须先于任何 turn 事件
- `message_update` 只能发生在 streaming 中
- `agent_end` 不能丢失，即使出错也要发
- `error` 不应该替代最终关闭事件

## 6. Loop 配置

### `AgentLoopConfig`

`AgentLoopConfig` 是 runtime 依赖注入层。

```python
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any


@dataclass(slots=True)
class BeforeToolCallContext:
    assistant_message: "AssistantMessage"
    tool_call: "ToolCallBlock"
    args: Any
    context: "AgentContext"


@dataclass(slots=True)
class AfterToolCallContext:
    assistant_message: "AssistantMessage"
    tool_call: "ToolCallBlock"
    args: Any
    result: Any
    is_error: bool
    context: "AgentContext"


@dataclass(slots=True)
class AgentLoopConfig:
    model: "Model"
    convert_to_llm: Callable[[list["AgentMessage"]], list["Message"] | Awaitable[list["Message"]]]
    transform_context: Callable[[list["AgentMessage"], AbortSignal | None], Awaitable[list["AgentMessage"]]] | None = None
    get_api_key: Callable[[str], str | Awaitable[str] | None] | None = None
    get_steering_messages: Callable[[], Awaitable[list["AgentMessage"]]] | None = None
    get_follow_up_messages: Callable[[], Awaitable[list["AgentMessage"]]] | None = None
    tool_execution: str = "parallel"
    before_tool_call: Callable[[BeforeToolCallContext, AbortSignal | None], Awaitable["BeforeToolCallResult | None"]] | None = None
    after_tool_call: Callable[[AfterToolCallContext, AbortSignal | None], Awaitable["AfterToolCallResult | None"]] | None = None
    stream_fn: Callable[..., Awaitable["AssistantMessageStream"]] | None = None
```

### 配套结果类型

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BeforeToolCallResult:
    block: bool = False
    reason: str | None = None


@dataclass(slots=True)
class AfterToolCallResult:
    content: list[Any] | None = None
    details: Any = None
    is_error: bool | None = None
```

## 7. Agent facade

### `Agent`

`Agent` 应该只做四件事：

1. 持有状态
2. 允许订阅事件
3. 启动 / 停止 loop
4. 更新基础配置

```python
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSubscription:
    unsubscribe: Callable[[], None]


class Agent:
    def __init__(self, state: "AgentState", loop_config: "AgentLoopConfig") -> None:
        self.state = state
        self.loop_config = loop_config
        self._subscribers: list[Callable[["AgentEvent"], None]] = []

    def subscribe(self, callback: Callable[["AgentEvent"], None]) -> Callable[[], None]:
        self._subscribers.append(callback)
        def _unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)
        return _unsubscribe

    async def prompt(self, message: "AgentMessage | str") -> None:
        ...

    async def continue_(self) -> None:
        ...

    def abort(self) -> None:
        ...

    def set_model(self, model: "Model") -> None:
        self.state.model = model

    def set_thinking_level(self, level: str) -> None:
        self.state.thinking_level = level

    def set_tools(self, tools: list["AgentTool"]) -> None:
        self.state.tools = tools
```

### 最小职责边界

`Agent` 不应该：

- 解析具体 provider payload
- 管 session file
- 做资源发现
- 做 Slack / Web / CLI 渲染

## 8. Loop 函数

### `loop.py`

建议分成几个显式函数：

```python
async def run_agent_loop(agent: Agent, *, signal: AbortSignal | None = None) -> None: ...
async def run_agent_loop_continue(agent: Agent, *, signal: AbortSignal | None = None) -> None: ...
async def stream_assistant_response(agent: Agent, messages: list["Message"], signal: AbortSignal | None = None) -> "AssistantMessage": ...
async def execute_tool_calls(agent: Agent, assistant_message: "AssistantMessage", signal: AbortSignal | None = None) -> list["ToolResultMessage"]: ...
async def prepare_tool_call(agent: Agent, assistant_message: "AssistantMessage", tool_call: "ToolCallBlock", signal: AbortSignal | None = None) -> Any: ...
```

### 关键语义

- 先生成 assistant response
- 再解析 tool calls
- 再执行工具
- 再把 tool results 放回上下文
- steering / follow-up 决定是否继续下一轮

## 9. Proxy

`proxy.py` 应该只负责 transport 替换。

建议接口：

```python
class StreamProxy(Protocol):
    async def stream(self, *args: Any, **kwargs: Any) -> "AssistantMessageStream": ...
```

不要把 proxy 混成业务逻辑层。

## 10. Compatibility

### 必须保留

- `sequential` / `parallel` 工具执行模式
- `beforeToolCall`
- `afterToolCall`
- steering 队列
- follow-up 队列
- abort 语义
- message update 的流式事件

### 可以后置

- 某些内部 debug 字段
- 过多的 UI 专用辅助事件
- 复杂的日志装饰逻辑

## 11. 推荐实现顺序

1. `state.py`
2. `tools.py`
3. `events.py`
4. `agent.py`
5. `loop.py`
6. `proxy.py`

先把最薄的 runtime 立起来，再让 `coding_agent`、`mom`、`web` 往上堆。

