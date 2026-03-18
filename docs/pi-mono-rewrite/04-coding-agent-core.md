# `pi-coding-agent` 核心运行机制

## 1. `AgentSession` 是业务中枢

[`packages/coding-agent/src/core/agent-session.ts`](../../packages/coding-agent/src/core/agent-session.ts) 不是简单 wrapper，它把这些职责合在一起：

- 订阅 `Agent` 事件
- 把 agent state 持久化到 session
- 管理 compaction / auto retry
- 管理 bash 执行与回放
- 管理 session switch / fork / tree navigation
- 承接 extension hooks

它相当于 Python 版里最需要复刻的 coordinator。

## 2. `ModelRegistry` 负责模型与鉴权

[`packages/coding-agent/src/core/model-registry.ts`](../../packages/coding-agent/src/core/model-registry.ts) 做了几件关键事：

- 从内建 `pi-ai` 模型表加载模型
- 读取 `models.json`
- 合并 provider-level 和 model-level override
- 为 custom provider 提供 fallback API key 解析
- 处理 OAuth provider 的动态模型修正
- 处理 `registerProvider()` / `unregisterProvider()`

Python 重写时，模型 registry 不能只是静态配置表，必须支持：

- runtime provider 注入
- provider 级 auth
- model override
- custom model definition

为了让 `AgentSession` 能真正连上 OpenAI-compatible / vLLM，Python 版还建议额外加入一个显式 provider registry 映射层：

- `PI_PROVIDER_REGISTRY`
- `PI_PROVIDER_REGISTRY_FILE`

这个 registry 负责把逻辑 provider、具体 API 变体、`base_url` 和 `api_key` 绑定起来。推荐 JSON 结构示例见 [28-coding-agent-persistence-schemas.md](./28-coding-agent-persistence-schemas.md)。

## 3. `ResourceLoader` 是资源发现层

[`packages/coding-agent/src/core/resource-loader.ts`](../../packages/coding-agent/src/core/resource-loader.ts) 统一加载：

- extensions
- skills
- prompt templates
- themes
- AGENTS.md / CLAUDE.md
- SYSTEM.md / APPEND_SYSTEM.md

它还做了：

- 路径归一化
- 冲突检测
- 目录与文件两种资源形式的适配
- metadata 追踪

Python 版建议把它拆成两个层：

- `resource_discovery`
- `resource_loading`

## 4. `ExtensionRunner` 是扩展执行器

[`packages/coding-agent/src/core/extensions/runner.ts`](../../packages/coding-agent/src/core/extensions/runner.ts) 是扩展系统的运行时。它负责：

- 注册 tools / commands / flags / shortcuts
- 发射扩展事件
- 提供 UI context
- 让扩展影响 context、provider payload、session tree、fork/switch/compact
- 处理冲突和优先级

它的设计重点不是“插件机制”本身，而是“插件可以影响整个 agent 生命周期”。

## 5. Python 迁移时的关键语义

### 必须保留

- session JSONL append-only tree
- fork / branch / tree / resume
- compaction summary
- model restore/fallback
- extension 注册和冲突检测
- before/after tool hooks
- before_provider_request / context mutation

### 可以简化

- TUI 主题热加载
- CLI 包管理命令的实现方式
- 复杂的短按/快捷键细节

## 6. 推荐 Python 包拆分

- `pi_cli`
- `pi_session`
- `pi_models`
- `pi_resources`
- `pi_extensions`
- `pi_runtime`

## 7. 核心伪代码：`AgentSession`

下面是 Python 版 `AgentSession` 的推荐形态。目标不是照搬 TypeScript，而是把当前 runtime 的职责边界显式化。

```python
class AgentSession:
    def __init__(
        self,
        *,
        agent: Agent,
        session_manager: SessionManager,
        settings_manager: SettingsManager,
        model_registry: ModelRegistry,
        resource_loader: ResourceLoader,
        tools: list[ToolDefinition],
        extensions: ExtensionRuntime | None = None,
        mode: Literal["interactive", "print", "rpc", "sdk"] = "interactive",
    ) -> None:
        self.agent = agent
        self.session_manager = session_manager
        self.settings_manager = settings_manager
        self.model_registry = model_registry
        self.resource_loader = resource_loader
        self.extensions = extensions
        self.mode = mode

        self._active_tools = tools
        self._pending_messages: list[Any] = []
        self._is_streaming = False
        self._is_compacting = False
        self._retry_attempt = 0
        self._current_model: Model | None = None
        self._current_thinking_level: str = "off"

    async def prompt(
        self,
        text: str,
        *,
        images: list[Any] | None = None,
        expand_prompt_templates: bool = True,
        streaming_behavior: Literal["steer", "follow_up", None] = None,
    ) -> None:
        """
        Main user entry point.

        Responsibilities:
        - expand prompt templates
        - run `input` extension hooks
        - execute extension commands when text starts with `/`
        - queue or forward message depending on streaming state
        - validate model / api key before sending
        - persist prompt-related entries to session
        """

    async def set_model(self, model: Model) -> None:
        """
        Switch the active model.

        Must:
        - verify api key availability
        - update agent runtime
        - persist model change entry
        - clamp thinking level to model capability
        - refresh default settings if needed
        - emit model_select event
        """

    async def cycle_model(self, direction: Literal["forward", "backward"] = "forward") -> Model | None:
        """
        Cycle within scoped models first; fall back to global model list.
        """

    async def set_thinking_level(self, level: str) -> None:
        """
        Clamp to model support and persist only if the effective level changes.
        """

    async def cycle_thinking_level(
        self,
        direction: Literal["forward", "backward"] = "forward",
    ) -> str | None:
        """
        Move through supported thinking levels for the active model.
        """

    def get_active_tool_names(self) -> list[str]:
        return [tool.name for tool in self._active_tools]

    def get_all_tools(self) -> list[ToolInfo]:
        return [ToolInfo(name=t.name, description=t.description, parameters=t.parameters) for t in self._active_tools]

    def set_active_tools(self, tool_names: list[str]) -> None:
        """
        Replace the active tool subset and rebuild the agent tool registry.
        """

    async def compact(self, *, custom_instructions: str | None = None) -> Any:
        """
        Trigger compaction synchronously with the current session state.
        Returns the compaction result object that will later be persisted.
        """

    async def fork(self, entry_id: str) -> "AgentSession":
        """
        Fork session at a specific entry.
        The new session should inherit the current runtime context but use a new session file.
        """

    async def navigate_tree(self, target_entry_id: str) -> None:
        """
        Move the current leaf to another branch, optionally summarizing the abandoned path.
        """

    async def reload(self) -> None:
        """
        Reload settings, resources, extensions and tool registry without losing the current session tree.
        """

    def abort(self) -> None:
        """Abort current streaming / tool / bash execution."""

    def is_idle(self) -> bool:
        return not self._is_streaming and not self._is_compacting

    def has_pending_messages(self) -> bool:
        return len(self._pending_messages) > 0
```

### `AgentSession` 的建议内部拆分

Python 版不建议把所有逻辑塞在一个类里。建议把内部实现拆成这些私有协作者：

- `PromptDispatcher`
- `ModelController`
- `ToolRegistryController`
- `SessionFlowController`
- `CompactionController`
- `ExtensionBindingController`
- `RetryController`
- `BashController`
- `ResourceRefreshController`
- `SessionTreeController`

## 8. 调用时序图

### 8.1 启动时序

```text
CLI / SDK / RPC
  -> build config (settings, auth, models, resources)
  -> construct SessionManager
  -> construct Agent
  -> construct AgentSession
  -> bind extensions
  -> resolve active model + thinking level
  -> load session context
  -> enter selected mode
```

### 8.2 `prompt()` 时序

```text
UI / RPC / SDK
  -> AgentSession.prompt(text)
  -> extension input hooks
  -> prompt template expansion
  -> command detection
  -> steering / follow-up queue decision
  -> agent.prompt()
  -> agent loop
  -> stream assistant message
  -> tool call / tool result
  -> persist session entries
  -> update UI / logs
```

### 8.3 tool call 时序

```text
assistant emits toolCall
  -> extension tool_call hook
  -> tool schema validation
  -> execute built-in or custom tool
  -> extension tool_result hook
  -> append toolResult message
  -> continue turn or stop
```

### 8.4 compaction 时序

```text
context usage exceeds threshold or /compact
  -> compute cut point
  -> collect messages + file ops
  -> extension session_before_compact hook
  -> summarize abandoned prefix
  -> append compaction entry
  -> reload session context
  -> resume prompt / turn
```

### 8.5 branch / tree 时序

```text
user requests fork / tree navigation
  -> locate branch target
  -> extension session_before_fork / session_before_tree hook
  -> optionally summarize abandoned branch
  -> update leaf pointer or create new session file
  -> restore labels and session metadata
  -> reload runtime state
```

### 8.6 reload 时序

```text
session_shutdown
  -> settings reload
  -> resource reload
  -> model registry refresh
  -> rebuild tools / extensions
  -> rebind UI context
  -> session_start
```

### `AgentSession` 的关键不变量

- session 只能追加，不能原地修改历史
- prompt/command/tool/compaction 都要回到同一个 session 轨道
- UI 模式变化不影响核心 runtime
- RPC 和 TUI 只是不同的宿主壳

## 9. 私有方法清单

建议 Python 版至少拆出这些私有方法，便于测试和分层：

- `_build_runtime()`
  - 组装 tools、extensions、system prompt、session context
- `_rebuild_system_prompt(active_tool_names)`
  - 基于工具、skills、prompt templates 重新生成 system prompt
- `_refresh_tool_registry()`
  - 重新构建 active tools、tool snippets、renderers
- `_refresh_current_model_from_registry()`
  - 从 session / settings / registry 同步当前模型
- `_try_execute_extension_command(text)`
  - 解析 `/cmd`，查找并执行扩展命令
- `_queue_prompt(text, images, behavior)`
  - 处理 streaming 时的 steer / follow-up 队列
- `_validate_model_or_raise()`
  - 确认当前 model 和 api key 可用
- `_apply_thinking_level_for_model(level)`
  - 结合模型能力 clamp thinking level
- `_record_model_change(model)`
  - 写入 session、settings、runtime 状态
- `_record_thinking_level_change(level)`
  - 写入 session 并同步 runtime
- `_execute_bash(command, options)`
  - 统一处理 bash prefix、stream callback、abort
- `_handle_tool_call(event)`
  - tool_call hook、权限 gate、执行工具
- `_handle_tool_result(event)`
  - tool_result hook、内容改写、错误标记
- `_maybe_start_compaction()`
  - 根据 context usage 决定是否自动 compaction
- `_apply_compaction_result(result)`
  - 持久化 compaction entry 并重建上下文
- `_fork_session(entry_id)`
  - 创建新 session 文件并复制路径
- `_navigate_tree(target_id, options)`
  - tree 切换、分支摘要、label 迁移
- `_reload_extensions_and_resources()`
  - reload 时重建 runtime
- `_emit_session_event(event_name, payload)`
  - 统一封装扩展事件发射

## 10. 私有协作者类图

建议 Python 版把 `AgentSession` 拆成一个编排器加多个私有协作者。类图可以按下面理解：

```text
AgentSession
  ├─ PromptDispatcher
  │    ├─ parse command / template
  │    ├─ queue steer / follow-up
  │    └─ normalize input images
  ├─ ModelController
  │    ├─ resolve current model
  │    ├─ validate api key
  │    └─ clamp thinking level
  ├─ ToolRegistryController
  │    ├─ build active tool set
  │    ├─ rebuild prompt snippets
  │    └─ refresh custom renderers
  ├─ SessionFlowController
  │    ├─ append session entries
  │    ├─ fork / tree / resume
  │    └─ label / name / metadata
  ├─ CompactionController
  │    ├─ compute cut point
  │    ├─ prepare compaction payload
  │    └─ apply compaction result
  ├─ BashController
  │    ├─ execute shell
  │    ├─ stream output
  │    └─ persist bashExecution messages
  ├─ ExtensionBindingController
  │    ├─ bind event bus
  │    ├─ bind ui context
  │    └─ bind command context
  ├─ RetryController
  │    ├─ backoff state
  │    └─ retry budget / abort
  └─ ResourceRefreshController
       ├─ reload settings
       ├─ reload resources
       └─ rebuild runtime
```

### 10.1 依赖方向

依赖关系建议是单向的：

```text
PromptDispatcher -> AgentSession (read-only)
ModelController -> AgentSession, ModelRegistry, SettingsManager
ToolRegistryController -> AgentSession, ExtensionRuntime, ResourceLoader
SessionFlowController -> AgentSession, SessionManager
CompactionController -> AgentSession, SessionManager, ModelController
BashController -> AgentSession, SettingsManager
ExtensionBindingController -> AgentSession, ExtensionRuntime
RetryController -> AgentSession, SettingsManager
ResourceRefreshController -> AgentSession, ResourceLoader, SettingsManager, ModelRegistry
```

### 10.2 方法依赖图

```text
prompt()
  -> _emit_session_event("input")
  -> _try_execute_extension_command()
  -> _queue_prompt()
  -> _validate_model_or_raise()
  -> agent.prompt()
  -> _handle_agent_event()

set_model()
  -> _validate_model_or_raise()
  -> _record_model_change()
  -> _apply_thinking_level_for_model()
  -> _refresh_tool_registry()   # when model/tool compatibility changes

set_thinking_level()
  -> _apply_thinking_level_for_model()
  -> _record_thinking_level_change()

compact()
  -> _maybe_start_compaction()
  -> _apply_compaction_result()
  -> _reload_extensions_and_resources()

fork()
  -> _fork_session()
  -> _reload_extensions_and_resources()

navigate_tree()
  -> _navigate_tree()
  -> _reload_extensions_and_resources()

reload()
  -> _reload_extensions_and_resources()
  -> _refresh_current_model_from_registry()
  -> _refresh_tool_registry()
```

### 10.3 协作者职责边界

- `AgentSession` 只做编排，不做复杂业务计算
- `PromptDispatcher` 只处理输入归一化，不碰 session 持久化
- `ModelController` 只处理模型与 thinking，不执行工具
- `SessionFlowController` 只管理树和元数据，不做 LLM 调用
- `CompactionController` 只处理 compaction，不决定 UI 呈现
- `BashController` 只管理 shell 生命周期，不直接改 prompt 逻辑
- `ExtensionBindingController` 只负责事件和上下文注入，不做业务分支
- `RetryController` 只管重试策略，不参与模型选择

## 11. 协作者类级接口草案

下面是更接近 Python 落地的私有协作者接口草案。它们不是公共 API，而是为了把 `AgentSession` 拆成可测试、可替换的模块。

### 11.1 `PromptDispatcher`

```python
class PromptDispatcher:
    def normalize_input(
        self,
        text: str,
        *,
        images: list[Any] | None = None,
        expand_prompt_templates: bool = True,
    ) -> tuple[str, list[Any] | None]:
        """Apply template expansion, image normalization and input sanitization."""

    def detect_command(self, text: str) -> tuple[str | None, str]:
        """Return (command_name, args) if text starts with '/', otherwise (None, text)."""

    def decide_queue_mode(
        self,
        *,
        is_streaming: bool,
        streaming_behavior: str | None,
        steering_mode: str,
        follow_up_mode: str,
    ) -> str:
        """Return 'direct', 'steer', or 'follow_up'."""

    def build_user_prompt(self, text: str, images: list[Any] | None = None) -> Any:
        """Create the runtime-specific user prompt object."""
```

### 11.2 `ModelController`

```python
class ModelController:
    def get_active_model(self) -> Model | None: ...
    def set_active_model(self, model: Model) -> None: ...
    def cycle_model(self, direction: str = "forward") -> Model | None: ...
    def validate_api_key(self, model: Model) -> str | None: ...
    def clamp_thinking_level(self, level: str) -> str: ...
    def set_thinking_level(self, level: str) -> str: ...
    def current_thinking_level(self) -> str: ...
```

### 11.3 `ToolRegistryController`

```python
class ToolRegistryController:
    def get_active_tool_names(self) -> list[str]: ...
    def set_active_tool_names(self, tool_names: list[str]) -> None: ...
    def list_all_tools(self) -> list[ToolInfo]: ...
    def refresh(self, *, include_all_extension_tools: bool = False) -> None: ...
    def rebuild_system_prompt(self) -> str: ...
    def get_tool_renderers(self) -> dict[str, Any]: ...
```

### 11.4 `SessionFlowController`

```python
class SessionFlowController:
    def append_user_message(self, text: str, images: list[Any] | None = None) -> str: ...
    def append_assistant_message(self, message: Any) -> str: ...
    def append_tool_result(self, message: Any) -> str: ...
    def append_bash_execution(self, command: str, result: Any) -> str: ...
    def append_custom_message(self, message: Any) -> str: ...
    def set_session_name(self, name: str) -> None: ...
    def set_label(self, entry_id: str, label: str | None) -> None: ...
    def fork(self, entry_id: str) -> str: ...
    def branch(self, entry_id: str | None) -> str: ...
    def navigate_tree(self, entry_id: str, *, summarize: bool = True) -> str: ...
    def get_context(self) -> SessionContext: ...
```

### 11.5 `CompactionController`

```python
class CompactionController:
    def should_compact(self, context_usage: ContextUsage, settings: CompactionSettings) -> bool: ...
    def prepare(self, entries: list[SessionEntry], settings: CompactionSettings) -> CompactionPreparation | None: ...
    async def summarize(
        self,
        preparation: CompactionPreparation,
        *,
        custom_instructions: str | None = None,
    ) -> CompactionResult: ...
    def apply(self, result: CompactionResult) -> str: ...
```

### 11.6 `BashController`

```python
class BashController:
    def execute(
        self,
        command: str,
        *,
        operations: BashOperations | None = None,
        stream_callback: Callable[[str], None] | None = None,
        signal: Any | None = None,
    ) -> BashResult: ...
    def record_result(self, command: str, result: BashResult, *, exclude_from_context: bool = False) -> str: ...
```

### 11.7 `ExtensionBindingController`

```python
class ExtensionBindingController:
    def bind_runtime(self, runtime: ExtensionRuntime) -> None: ...
    def bind_ui_context(self, ui_context: ExtensionUIContext | None) -> None: ...
    def bind_command_context(self, ctx: ExtensionCommandContextActions | None) -> None: ...
    def emit(self, event: ExtensionEvent) -> None: ...
    def emit_tool_call(self, event: ToolCallEvent) -> ToolCallEventResult | None: ...
    def emit_tool_result(self, event: ToolResultEvent) -> ToolResultEventResult | None: ...
```

### 11.8 `RetryController`

```python
class RetryController:
    def get_budget(self) -> tuple[int, int, int]: ...
    def should_retry(self, error: Exception) -> bool: ...
    def next_delay_ms(self, attempt: int) -> int: ...
    def reset(self) -> None: ...
```

### 11.9 类级依赖规则

- 协作者只依赖 `AgentSession` 暴露的只读状态和注入服务
- 协作者之间不直接互相调用，统一通过 `AgentSession` 协调
- 所有写入 session 的动作必须最终经过 `SessionFlowController`
- 所有模型切换必须最终经过 `ModelController`
- 所有 compaction 决策必须最终经过 `CompactionController`
