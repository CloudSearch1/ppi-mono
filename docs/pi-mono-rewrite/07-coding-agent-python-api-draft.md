# `pi-coding-agent` Python 接口草案

这份草案按“类 / 方法 / 数据结构”组织，目标是让 Python 实现可以直接按接口开工。

## 1. 核心数据结构

### 1.1 Session

```python
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

@dataclass
class SessionHeader:
    type: Literal["session"] = "session"
    version: int = 3
    id: str = ""
    timestamp: str = ""
    cwd: str = ""
    parent_session: Optional[str] = None

@dataclass
class SessionEntryBase:
    type: str
    id: str
    parent_id: Optional[str]
    timestamp: str

@dataclass
class MessageEntry(SessionEntryBase):
    type: Literal["message"] = "message"
    message: Any = None

@dataclass
class ModelChangeEntry(SessionEntryBase):
    type: Literal["model_change"] = "model_change"
    provider: str = ""
    model_id: str = ""

@dataclass
class ThinkingLevelChangeEntry(SessionEntryBase):
    type: Literal["thinking_level_change"] = "thinking_level_change"
    thinking_level: str = "off"

@dataclass
class CompactionEntry(SessionEntryBase):
    type: Literal["compaction"] = "compaction"
    summary: str = ""
    first_kept_entry_id: str = ""
    tokens_before: int = 0
    details: dict[str, Any] | None = None
    from_hook: bool | None = None

@dataclass
class BranchSummaryEntry(SessionEntryBase):
    type: Literal["branch_summary"] = "branch_summary"
    from_id: str = ""
    summary: str = ""
    details: dict[str, Any] | None = None
    from_hook: bool | None = None
```

### 1.2 Settings

```python
@dataclass
class CompactionSettings:
    enabled: bool = True
    reserve_tokens: int = 16384
    keep_recent_tokens: int = 20000

@dataclass
class RetrySettings:
    enabled: bool = True
    max_retries: int = 3
    base_delay_ms: int = 2000
    max_delay_ms: int = 60000

@dataclass
class Settings:
    default_provider: str | None = None
    default_model: str | None = None
    default_thinking_level: str | None = None
    steering_mode: str = "one-at-a-time"
    follow_up_mode: str = "one-at-a-time"
    transport: str = "sse"
    compaction: CompactionSettings = field(default_factory=CompactionSettings)
    retry: RetrySettings = field(default_factory=RetrySettings)
```

### 1.3 Tools

```python
@dataclass
class ToolDefinition:
    name: str
    label: str
    description: str
    parameters: dict[str, Any]
    prompt_snippet: str | None = None
    prompt_guidelines: str | None = None
    execute: Any | None = None
    render_call: Any | None = None
    render_result: Any | None = None

@dataclass
class ToolInfo:
    name: str
    description: str
    parameters: dict[str, Any]
```

### 1.4 Extension

```python
@dataclass
class ExtensionFlag:
    name: str
    description: str | None = None
    type: Literal["boolean", "string"] = "boolean"
    default: bool | str | None = None

@dataclass
class RegisteredCommand:
    name: str
    description: str | None
    handler: Any
```

## 2. 核心类

### 2.1 `SessionManager`

```python
class SessionManager:
    def append_message(self, message: Any) -> str: ...
    def append_model_change(self, provider: str, model_id: str) -> str: ...
    def append_thinking_level_change(self, level: str) -> str: ...
    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int, details: dict | None = None) -> str: ...
    def append_custom_entry(self, custom_type: str, data: Any = None) -> str: ...
    def append_custom_message(self, custom_type: str, content: Any, display: bool, details: Any = None) -> str: ...
    def append_label(self, target_id: str, label: str | None) -> str: ...
    def append_session_info(self, name: str) -> str: ...

    def get_entries(self) -> list[Any]: ...
    def get_tree(self) -> list[Any]: ...
    def get_branch(self, from_id: str | None = None) -> list[Any]: ...
    def build_session_context(self) -> Any: ...
    def get_leaf_id(self) -> str | None: ...
    def get_session_name(self) -> str | None: ...
    def set_session_name(self, name: str) -> None: ...

    @classmethod
    def open(cls, path: str, session_dir: str | None = None) -> "SessionManager": ...
    @classmethod
    def fork_from(cls, source_path: str, target_cwd: str, session_dir: str | None = None) -> "SessionManager": ...
```

### 2.2 `SettingsManager`

```python
class SettingsManager:
    def get_default_model(self) -> str | None: ...
    def set_default_model(self, provider: str, model_id: str) -> None: ...
    def get_steering_mode(self) -> str: ...
    def set_steering_mode(self, mode: str) -> None: ...
    def get_follow_up_mode(self) -> str: ...
    def set_follow_up_mode(self, mode: str) -> None: ...
    def get_compaction_settings(self) -> CompactionSettings: ...
    def get_retry_settings(self) -> RetrySettings: ...
    def get_enable_skill_commands(self) -> bool: ...
    def get_block_images(self) -> bool: ...
    def get_enabled_models(self) -> list[str] | None: ...
    def reload(self) -> None: ...
    def apply_overrides(self, overrides: dict[str, Any]) -> None: ...
```

### 2.3 `ModelRegistry`

```python
class ModelRegistry:
    def get_model(self, provider: str, model_id: str) -> Any: ...
    def list_models(self) -> list[Any]: ...
    def refresh(self) -> None: ...
    def register_provider(self, name: str, config: dict[str, Any]) -> None: ...
    def unregister_provider(self, name: str) -> None: ...
    def get_api_key(self, model: Any) -> str | None: ...
```

### 2.4 `ResourceLoader`

```python
class ResourceLoader:
    def reload(self) -> None: ...
    def load_skills(self) -> list[Any]: ...
    def load_prompt_templates(self) -> list[Any]: ...
    def load_themes(self) -> list[Any]: ...
    def discover_extensions(self) -> list[str]: ...
    def extend_resources(self, paths: dict[str, list[str]]) -> None: ...
```

### 2.5 `AgentSession`

```python
class AgentSession:
    async def prompt(self, text: str, *, expand_prompt_templates: bool = True, streaming_behavior: str | None = None) -> None: ...
    async def set_model(self, model: Any) -> None: ...
    async def cycle_model(self, direction: str = "forward") -> Any | None: ...
    async def set_thinking_level(self, level: str) -> None: ...
    async def cycle_thinking_level(self, direction: str = "forward") -> Any | None: ...
    def set_active_tools(self, tool_names: list[str]) -> None: ...
    def get_active_tool_names(self) -> list[str]: ...
    def get_all_tools(self) -> list[ToolInfo]: ...
    async def compact(self, custom_instructions: str | None = None) -> Any: ...
    async def fork(self, entry_id: str) -> Any: ...
    async def navigate_tree(self, target_id: str, *, summary: str | None = None) -> Any: ...
    async def reload(self) -> None: ...
    def abort(self) -> None: ...
    def is_idle(self) -> bool: ...
    def has_pending_messages(self) -> bool: ...
```

### 2.6 `ExtensionAPI`

```python
class ExtensionAPI(Protocol):
    def on(self, event_name: str, handler: Any) -> None: ...
    def register_tool(self, tool: ToolDefinition) -> None: ...
    def register_command(self, command: RegisteredCommand) -> None: ...
    def register_flag(self, flag: ExtensionFlag) -> None: ...
    def register_provider(self, name: str, config: dict[str, Any]) -> None: ...
    def send_message(self, message: Any) -> None: ...
    def send_user_message(self, content: str) -> None: ...
    def get_active_tools(self) -> list[str]: ...
    def set_active_tools(self, tool_names: list[str]) -> None: ...
    def set_model(self, model: Any) -> None: ...
    def set_thinking_level(self, level: str) -> None: ...
```

## 3. RPC 草案

### 3.1 请求

建议直接保留当前语义：

- `prompt`
- `steer`
- `follow_up`
- `abort`
- `new_session`
- `get_state`
- `set_model`
- `cycle_model`
- `get_available_models`
- `set_thinking_level`
- `cycle_thinking_level`
- `set_steering_mode`
- `set_follow_up_mode`
- `compact`
- `set_auto_compaction`
- `set_auto_retry`
- `abort_retry`
- `bash`
- `abort_bash`
- `get_session_stats`
- `export_html`
- `switch_session`
- `fork`
- `get_fork_messages`
- `get_last_assistant_text`
- `set_session_name`
- `get_commands`

### 3.2 状态

```python
@dataclass
class RpcSessionState:
    model: Any | None
    thinking_level: str
    is_streaming: bool
    is_compacting: bool
    steering_mode: str
    follow_up_mode: str
    session_name: str | None
    session_path: str | None
```

## 4. 事件建议

建议 Python 版采用统一事件对象：

```python
@dataclass
class Event:
    type: str
    payload: dict[str, Any]
```

然后按以下分组分发：

- lifecycle
- prompt / input
- model / thinking
- tool
- session
- compaction
- extension UI

## 5. 设计原则

- 尽量让数据结构显式化
- 尽量让状态变化通过事件驱动
- session 文件永远可回放
- RPC 和 interactive 使用同一套核心 runtime

