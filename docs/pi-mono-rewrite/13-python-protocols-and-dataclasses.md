# Python `dataclass` / `Protocol` 接口草案

这份草案把前面的包结构进一步收敛成可实现的 Python 类型边界。

目标不是把所有细节一次性定死，而是先把：

- 哪些对象应该是 `dataclass`
- 哪些边界应该是 `Protocol`
- 哪些状态应该是只读快照

明确下来，方便后面分阶段实现。

---

## 1. 设计原则

1. 业务状态优先用 `dataclass` 或 `pydantic.BaseModel`
2. 可替换实现优先用 `Protocol`
3. 长生命周期服务用显式工厂，不要在模块 import 时初始化
4. 事件流和持久化记录尽量使用独立类型，不要复用 UI 组件对象
5. LLM 协议对象、session 记录、扩展事件要区分“运行中状态”和“持久化状态”

---

## 2. 公共基础类型

建议先放在 `pimono.shared`：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, runtime_checkable


JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None


@dataclass(slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class TextContent:
    type: str = "text"
    text: str = ""


@dataclass(slots=True)
class ImageContent:
    type: str = "image"
    data: str = ""
    mime_type: str = "image/png"


ContentBlock = TextContent | ImageContent


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(slots=True)
class ToolResult:
    tool_call_id: str
    name: str
    content: list[ContentBlock]
    details: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False


@dataclass(slots=True)
class ModelRef:
    provider: str
    model_id: str


@dataclass(slots=True)
class ContextUsage:
    tokens: Usage
    model: ModelRef | None = None


@runtime_checkable
class AbortSignal(Protocol):
    @property
    def aborted(self) -> bool: ...

    def add_event_listener(self, event: str, callback: Callable[[], None]) -> None: ...

    def remove_event_listener(self, event: str, callback: Callable[[], None]) -> None: ...
```

---

## 3. `pi_core` 接口草案

### 3.1 消息模型

```python
@dataclass(slots=True)
class UserMessage:
    role: str = "user"
    content: list[ContentBlock] = field(default_factory=list)
    timestamp: int = 0


@dataclass(slots=True)
class AssistantMessage:
    role: str = "assistant"
    content: list[ContentBlock] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    timestamp: int = 0
    stop_reason: str | None = None
    usage: Usage | None = None
    error_message: str | None = None


@dataclass(slots=True)
class ToolResultMessage:
    role: str = "toolResult"
    content: list[ContentBlock] = field(default_factory=list)
    tool_call_id: str = ""
    timestamp: int = 0


AgentMessage = UserMessage | AssistantMessage | ToolResultMessage | Any
```

### 3.2 事件模型

```python
@dataclass(slots=True)
class MessageStartEvent:
    type: str
    message: AgentMessage


@dataclass(slots=True)
class MessageUpdateEvent:
    type: str
    assistant_delta: str | None = None


@dataclass(slots=True)
class MessageEndEvent:
    type: str
    message: AgentMessage


@dataclass(slots=True)
class ToolExecutionStartEvent:
    type: str
    tool_call: ToolCall


@dataclass(slots=True)
class ToolExecutionUpdateEvent:
    type: str
    tool_call_id: str
    content: list[ContentBlock]


@dataclass(slots=True)
class ToolExecutionEndEvent:
    type: str
    tool_call: ToolCall
    result: ToolResult


AgentEvent = (
    MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
    | Any
)
```

### 3.3 核心协议

```python
@runtime_checkable
class Transport(Protocol):
    async def stream(self, model: ModelRef, messages: list[AgentMessage], *, signal: AbortSignal | None = None) -> Any: ...


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]

    async def execute(
        self,
        tool_call_id: str,
        args: dict[str, Any],
        *,
        signal: AbortSignal | None = None,
        on_update: Callable[[list[ContentBlock], dict[str, Any] | None], None] | None = None,
    ) -> ToolResult: ...


@runtime_checkable
class Agent(Protocol):
    @property
    def state(self) -> Any: ...

    async def prompt(self, message: AgentMessage | str | list[AgentMessage]) -> None: ...
    async def continue_(self) -> None: ...
    def abort(self) -> None: ...
    def subscribe(self, callback: Callable[[AgentEvent], None]) -> Callable[[], None]: ...
```

### 3.4 推荐 `dataclass`

```python
@dataclass(slots=True)
class AgentState:
    system_prompt: str
    model: ModelRef
    thinking_level: str = "off"
    tools: list[Tool] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    is_streaming: bool = False
    stream_message: AssistantMessage | None = None
    pending_tool_calls: set[str] = field(default_factory=set)
    error: str | None = None


@dataclass(slots=True)
class AgentLoopConfig:
    transport: Transport
    convert_to_llm: Callable[[list[AgentMessage]], list[dict[str, Any]]]
    transform_context: Callable[[list[AgentMessage]], list[AgentMessage]] | None = None
    tool_execution_mode: str = "parallel"
    before_tool_call: Callable[..., Any] | None = None
    after_tool_call: Callable[..., Any] | None = None
```

---

## 4. `pi_session` 接口草案

### 4.1 session entry

```python
@dataclass(slots=True)
class SessionHeader:
    type: str = "session"
    version: int = 3
    id: str = ""
    timestamp: str = ""
    cwd: str = ""
    parent_session: str | None = None


@dataclass(slots=True)
class SessionMessageEntry:
    type: str = "message"
    id: str = ""
    parent_id: str | None = None
    timestamp: str = ""
    message: AgentMessage | None = None


@dataclass(slots=True)
class CompactionEntry:
    type: str = "compaction"
    id: str = ""
    parent_id: str | None = None
    timestamp: str = ""
    summary: str = ""
    first_kept_entry_id: str = ""
    tokens_before: int = 0
    details: dict[str, Any] | None = None
    from_hook: bool = False


@dataclass(slots=True)
class BranchSummaryEntry:
    type: str = "branch_summary"
    id: str = ""
    parent_id: str | None = None
    timestamp: str = ""
    from_id: str = ""
    summary: str = ""
    details: dict[str, Any] | None = None
    from_hook: bool = False
```

### 4.2 session tree

```python
@dataclass(slots=True)
class SessionTreeNode:
    entry: Any
    children: list["SessionTreeNode"] = field(default_factory=list)
    label: str | None = None


@dataclass(slots=True)
class SessionContext:
    messages: list[AgentMessage]
    thinking_level: str
    model: ModelRef | None
```

### 4.3 session repository protocol

```python
@runtime_checkable
class SessionRepository(Protocol):
    def append_message(self, message: AgentMessage) -> str: ...
    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int) -> str: ...
    def append_model_change(self, provider: str, model_id: str) -> str: ...
    def append_thinking_level_change(self, level: str) -> str: ...
    def append_custom_entry(self, custom_type: str, data: Any = None) -> str: ...
    def append_custom_message_entry(self, custom_type: str, content: Any, display: bool, details: Any = None) -> str: ...
    def append_label_change(self, target_id: str, label: str | None) -> str: ...
    def build_context(self) -> SessionContext: ...
    def branch(self, entry_id: str) -> None: ...
    def branch_with_summary(self, entry_id: str | None, summary: str) -> str: ...
    def create_branched_session(self, leaf_id: str) -> str | None: ...
```

### 4.4 compaction / branch summary

```python
@dataclass(slots=True)
class CompactionResult:
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class BranchSummaryResult:
    summary: str
    from_id: str
    details: dict[str, Any] | None = None
```

---

## 5. `pi_resources` 接口草案

### 5.1 resource objects

```python
@dataclass(slots=True)
class ResourceDiagnostic:
    type: str
    message: str
    path: str | None = None
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class PromptTemplate:
    name: str
    description: str
    content: str
    source_path: str


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    content: str
    source_path: str


@dataclass(slots=True)
class Theme:
    name: str
    source_path: str | None = None
    colors: dict[str, str] = field(default_factory=dict)
```

### 5.2 loader protocol

```python
@runtime_checkable
class ResourceLoader(Protocol):
    async def reload(self) -> None: ...
    def get_extensions(self) -> Any: ...
    def get_skills(self) -> tuple[list[Skill], list[ResourceDiagnostic]]: ...
    def get_prompts(self) -> tuple[list[PromptTemplate], list[ResourceDiagnostic]]: ...
    def get_themes(self) -> tuple[list[Theme], list[ResourceDiagnostic]]: ...
    def get_agents_files(self) -> list[tuple[str, str]]: ...
    def get_system_prompt(self) -> str | None: ...
```

---

## 6. `pi_extensions` 接口草案

### 6.1 extension event / context

```python
@dataclass(slots=True)
class ExtensionEvent:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RegisteredTool:
    definition: Any
    extension_path: str


@runtime_checkable
class ExtensionRunner(Protocol):
    async def emit(self, event: ExtensionEvent) -> Any: ...
    def has_handlers(self, event_type: str) -> bool: ...
    def get_command(self, name: str) -> Any | None: ...
    def get_all_registered_tools(self) -> list[RegisteredTool]: ...
    def get_registered_commands(self) -> list[Any]: ...
```

### 6.2 UI context

```python
@runtime_checkable
class ExtensionUIContext(Protocol):
    async def select(self, title: str, options: list[str], *, timeout: float | None = None) -> str | None: ...
    async def confirm(self, title: str, message: str, *, timeout: float | None = None) -> bool: ...
    async def input(self, title: str, placeholder: str | None = None, *, timeout: float | None = None) -> str | None: ...
    def notify(self, message: str, kind: str = "info") -> None: ...
    def set_status(self, key: str, text: str | None) -> None: ...
    def set_widget(self, key: str, content: list[str] | None) -> None: ...
    def set_footer(self, factory: Any | None) -> None: ...
    def set_header(self, factory: Any | None) -> None: ...
    def set_title(self, title: str) -> None: ...
```

### 6.3 extension API

```python
@runtime_checkable
class ExtensionAPI(Protocol):
    def register_tool(self, tool: Any) -> None: ...
    def register_command(self, name: str, handler: Callable[..., Any]) -> None: ...
    def register_flag(self, name: str, flag_type: str) -> None: ...
    def on(self, event_name: str, handler: Callable[..., Any]) -> None: ...
```

---

## 7. `pi_cli` 接口草案

### 7.1 CLI args

```python
@dataclass(slots=True)
class Args:
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    thinking: str | None = None
    continue_session: bool = False
    resume: bool = False
    mode: str | None = None
    no_session: bool = False
    session: str | None = None
    fork: str | None = None
    session_dir: str | None = None
    models: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    no_tools: bool = False
    extensions: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    prompt_templates: list[str] = field(default_factory=list)
    themes: list[str] = field(default_factory=list)
    print_mode: bool = False
    export: str | None = None
    verbose: bool = False
    messages: list[str] = field(default_factory=list)
    file_args: list[str] = field(default_factory=list)
```

### 7.2 mode runner protocol

```python
@runtime_checkable
class ModeRunner(Protocol):
    async def run(self, session: Any, options: Any) -> None: ...
```

### 7.3 session factory

```python
@dataclass(slots=True)
class CreateAgentSessionOptions:
    cwd: str | None = None
    agent_dir: str | None = None
    auth_storage: Any | None = None
    model_registry: Any | None = None
    model: Any | None = None
    thinking_level: str | None = None
    scoped_models: list[Any] = field(default_factory=list)
    tools: list[Any] = field(default_factory=list)
    custom_tools: list[Any] = field(default_factory=list)
    resource_loader: Any | None = None
    session_manager: Any | None = None
    settings_manager: Any | None = None


@dataclass(slots=True)
class CreateAgentSessionResult:
    session: Any
    extensions_result: Any
    model_fallback_message: str | None = None
```

---

## 8. 推荐实现顺序

1. `pimono.shared`
2. `pimono.pi_core`
3. `pimono.pi_session`
4. `pimono.pi_resources`
5. `pimono.pi_extensions`
6. `pimono.pi_cli`

如果只能先落一条主链，建议先实现：

```text
Args -> CreateAgentSessionOptions -> AgentState -> SessionContext -> SessionRepository
```

这条链已经足够跑起最小可用的命令行对话、存储和恢复。
