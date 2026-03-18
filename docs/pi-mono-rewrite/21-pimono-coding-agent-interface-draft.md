# `ppi_coding_agent` 第一版接口草案

这份文档把 `pimono.coding_agent` 对应的 Python 实现边界收紧到“接口层”。

它与 `18-pimono-ai-code-skeleton.md` 和 `19-pimono-agent-core-interface.md` 配套：

- `pimono.ai` 负责协议
- `pimono.agent_core` 负责 loop
- `pimono.coding_agent` 负责 session / settings / models / resources / extensions 的业务中枢

## 1. 设计目标

`coding_agent` 这一层要做的是把多个可替换协作者组装起来：

- `Agent`
- `SessionManager`
- `SettingsManager`
- `ModelRegistry`
- `ResourceLoader`
- `ExtensionRunner`

核心原则：

1. 组装逻辑和业务逻辑分开
2. 持久化和运行时状态分开
3. 资源发现和资源应用分开
4. 扩展注册和扩展执行分开

## 2. 建议目录

```text
python/src/ppi_coding_agent/
├── __init__.py
├── cli/
│   ├── __init__.py
│   └── main.py
└── core/
    ├── __init__.py
    ├── agent_session.py
    ├── auth.py
    ├── compaction.py
    ├── extensions.py
    ├── model_registry.py
    ├── resource_loader.py
    ├── rpc.py
    ├── session.py
    ├── settings.py
    └── tools.py
```

如果后续要继续拆细，还可以进一步分成：

- `session/`
- `settings/`
- `models/`
- `resources/`
- `extensions/`
- `tools/`

## 3. 关键对象

### `AgentSession`

`AgentSession` 是业务协调器，而不是单纯的 facade。

职责应包括：

- prompt 入口
- continue 入口
- model / thinking 切换
- tool 集合切换
- session fork / branch / tree navigation
- compaction
- extension hook 协调
- resource reload

### `ModelRegistry`

负责：

- builtin model lookup
- custom model config
- provider 注册和注销
- API key / OAuth fallback
- default model resolution

### `SessionManager`

负责：

- append-only session tree
- branch / fork / resume
- session metadata
- compaction / branch summary entry
- context build

### `SettingsManager`

负责：

- global settings
- project settings
- merge 和 override
- persistence
- migration

### `ResourceLoader`

负责：

- skills
- prompts
- themes
- extensions
- AGENTS / SYSTEM 文件
- diagnostics

### `ExtensionRunner`

负责：

- tool / command / flag / shortcut 注册
- before / after hooks
- session lifecycle hooks
- provider request hook
- context mutation

## 4. 接口草案

### 4.1 `AgentSessionOptions`

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AgentSessionOptions:
    agent: "Agent | None" = None
    session_manager: "SessionManager | None" = None
    settings_manager: "SettingsManager | None" = None
    model_registry: "ModelRegistry | None" = None
    resource_loader: "ResourceLoader | None" = None
    extension_runner: "ExtensionRunner | None" = None
    base_tools: list["ToolDefinition"] = field(default_factory=list)
    cwd: str = ""
    agent_dir: str = ""
```

### 4.2 `AgentSession`

```python
class AgentSession:
    def __init__(self, options: AgentSessionOptions | None = None) -> None: ...

    async def prompt(self, message: str) -> None: ...
    async def continue_(self) -> None: ...
    async def compact(self) -> None: ...
    async def fork(self) -> str: ...
    async def reload(self) -> None: ...
    def abort(self) -> None: ...
```

### 4.3 `SessionManager`

```python
from typing import Protocol


class SessionManager(Protocol):
    def append_entry(self, entry: "SessionEntry") -> None: ...
    def append_message(self, message: "Message") -> None: ...
    def get_entries(self) -> list["SessionEntry"]: ...
    def build_context(self, leaf_id: str | None = None) -> "SessionContext": ...
    def get_tree(self) -> list["SessionTreeNode"]: ...
```

### 4.4 `SettingsManager`

```python
class SettingsManager(Protocol):
    def get_global_settings(self) -> "Settings": ...
    def get_project_settings(self) -> "Settings": ...
    def get_default_model(self) -> str | None: ...
    def get_default_provider(self) -> str | None: ...
    def get_default_thinking_level(self) -> str | None: ...
    def get_block_images(self) -> bool: ...
    def save(self) -> None: ...
```

### 4.5 `ModelRegistry`

```python
class ModelRegistry(Protocol):
    def get_model(self, provider: str, model_id: str) -> "Model": ...
    def list_models(self, provider: str | None = None) -> list["Model"]: ...
    def register_provider(self, provider: str, payload: Any) -> None: ...
    def unregister_provider(self, provider: str) -> None: ...
    async def get_api_key(self, model: "Model") -> str | None: ...
```

### 4.6 `ResourceLoader`

```python
class ResourceLoader(Protocol):
    def load(self) -> "ResourceLoadResult": ...
    def reload(self) -> None: ...
    def get_diagnostics(self) -> list["ResourceDiagnostic"]: ...
```

### 4.7 `ExtensionRunner`

```python
class ExtensionRunner(Protocol):
    def emit(self, event: "ExtensionEvent") -> None: ...
    def load(self) -> None: ...
    def register_tool(self, name: str, tool: Any) -> None: ...
    def register_command(self, name: str, handler: Any) -> None: ...
    def register_provider(self, name: str, provider: Any) -> None: ...
```

## 5. `AgentSession` 内部协作者

为了避免一个类过重，建议内部拆成这些协作者：

- `PromptDispatcher`
- `ModelController`
- `ToolRegistryController`
- `SessionFlowController`
- `CompactionController`
- `ExtensionBindingController`
- `RetryController`
- `ResourceRefreshController`

这些协作者不一定需要对外暴露，但应在实现时对应明确。

## 6. 关键运行流程

### 6.1 初始化流程

```text
CLI / SDK
  -> build auth/settings/models/resources
  -> create SessionManager
  -> create Agent
  -> create AgentSession
  -> load resources
  -> bind extensions
  -> resolve active model / thinking level
  -> build initial context
```

### 6.2 `prompt()` 流程

```text
user prompt
  -> expand prompt templates
  -> apply input hooks
  -> dispatch slash commands if needed
  -> append message to session
  -> call Agent.prompt()
  -> persist agent events
```

### 6.3 `reload()` 流程

```text
reload request
  -> refresh settings
  -> reload resources
  -> rebuild extensions
  -> refresh model registry
  -> update active tools
```

## 7. 与 `ppi_ai` / `ppi_agent_core` 的关系

`coding_agent` 只依赖下面几个稳定输入：

- `Model`
- `Message`
- `Agent`
- `AgentState`
- `AgentEvent`
- `AgentTool`

它不应该直接依赖 provider SDK 细节，也不应该把 UI、Slack 或 pod 管理逻辑混进来。

## 8. 兼容点

### 必须保留

- append-only session tree
- fork / branch / resume
- compaction summary
- provider registration
- model fallback / restore
- extension hook 机制
- resource discovery 和 diagnostics

### 可以后置

- 复杂 TUI 细节
- 热加载 UI 组件
- 某些 CLI 辅助输出

## 9. 和当前 Python 代码的对接建议

如果你要继续演进 `python/src/ppi_coding_agent/`，建议按这个优先级：

1. `core/session.py`
2. `core/settings.py`
3. `core/model_registry.py`
4. `core/resource_loader.py`
5. `core/extensions.py`
6. `core/agent_session.py`

先把这六个角色的接口定稳，再往下补实现。

