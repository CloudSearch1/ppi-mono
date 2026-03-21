# Python 版目录结构与接口草案

这份文档把前面的分析收敛成一个可以直接启动实现的 Python 包布局。

目标不是“一次把所有功能写完”，而是先把边界、协议和可替换接口定死，避免后面重写时出现职责混淆。

## 1. 总体包分层

建议拆成五层：

1. `pimono.ai`：LLM 协议层和 provider 适配层
2. `pimono.agent_core`：agent 状态机、工具执行、stream/loop 编排
3. `pimono.coding_agent`：会话、设置、模型注册、资源发现、扩展系统
4. `pimono.mom`：Slack bot、workspace、sandbox、事件同步
5. `pimono.pods`：pod / vLLM / remote CLI / model planning

如果要保留 Web 端协议辅助层，可以再加：

6. `pimono.web`：storage、attachments、artifacts、proxy、消息转换

## 2. 推荐目录树

```text
pi-mono-py/
├── pyproject.toml
├── README.md
├── src/
│   └── pimono/
│       ├── __init__.py
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── messages.py
│       │   ├── types.py
│       │   ├── events.py
│       │   ├── stream.py
│       │   ├── registry.py
│       │   ├── api_keys.py
│       │   ├── validation.py
│       │   ├── replay.py
│       │   ├── transport/
│       │   │   ├── __init__.py
│       │   │   ├── http.py
│       │   │   ├── sse.py
│       │   │   └── auth.py
│       │   └── providers/
│       │       ├── __init__.py
│       │       ├── openai_completions.py
│       │       ├── openai_responses.py
│       │       ├── anthropic.py
│       │       └── ...
│       ├── agent_core/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── loop.py
│       │   ├── state.py
│       │   ├── tools.py
│       │   ├── events.py
│       │   ├── proxy.py
│       │   └── compatibility.py
│       ├── coding_agent/
│       │   ├── __init__.py
│       │   ├── sdk.py
│       │   ├── main.py
│       │   ├── session/
│       │   │   ├── __init__.py
│       │   │   ├── manager.py
│       │   │   ├── types.py
│       │   │   └── compaction.py
│       │   ├── settings/
│       │   │   ├── __init__.py
│       │   │   ├── manager.py
│       │   │   └── storage.py
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── registry.py
│       │   │   └── resolver.py
│       │   ├── resources/
│       │   │   ├── __init__.py
│       │   │   ├── loader.py
│       │   │   └── diagnostics.py
│       │   ├── extensions/
│       │   │   ├── __init__.py
│       │   │   ├── runner.py
│       │   │   ├── types.py
│       │   │   └── wrapper.py
│       │   ├── auth/
│       │   │   ├── __init__.py
│       │   │   └── storage.py
│       │   └── utils/
│       │       ├── __init__.py
│       │       └── shell.py
│       ├── mom/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── slack/
│       │   │   ├── __init__.py
│       │   │   ├── bot.py
│       │   │   ├── context.py
│       │   │   └── types.py
│       │   ├── workspace/
│       │   │   ├── __init__.py
│       │   │   ├── store.py
│       │   │   ├── attachments.py
│       │   │   └── sync.py
│       │   ├── sandbox/
│       │   │   ├── __init__.py
│       │   │   ├── executor.py
│       │   │   └── config.py
│       │   └── events/
│       │       ├── __init__.py
│       │       └── scheduler.py
│       ├── pods/
│       │   ├── __init__.py
│       │   ├── cli.py
│       │   ├── config.py
│       │   ├── registry.py
│       │   ├── remote.py
│       │   ├── model_plan.py
│       │   ├── vllm.py
│       │   └── agent_cli.py
│       └── web/
│           ├── __init__.py
│           ├── storage.py
│           ├── attachments.py
│           ├── artifacts.py
│           ├── proxy.py
│           └── messages.py
└── tests/
    ├── ai/
    ├── agent_core/
    ├── coding_agent/
    ├── mom/
    ├── pods/
    └── web/
```

## 3. 核心抽象接口

### `pimono.ai`

建议用 `Protocol`、`dataclass`、`pydantic` 来稳定外部协议。

核心类型：

- `Model`
- `Message`
- `Context`
- `Tool`
- `ToolCall`
- `ToolResult`
- `Usage`
- `AssistantMessage`
- `AssistantMessageEvent`

核心接口：

```python
class Provider(Protocol):
    async def stream(self, model: Model, context: Context, options: StreamOptions) -> AssistantMessageStream: ...
    async def complete(self, model: Model, context: Context, options: StreamOptions) -> AssistantMessage: ...


class AssistantMessageStream(Protocol):
    def __aiter__(self) -> AsyncIterator[AssistantMessageEvent]: ...
    async def result(self) -> AssistantMessage: ...


class ApiRegistry(Protocol):
    def register(self, name: str, provider: Provider) -> None: ...
    def get(self, name: str) -> Provider: ...
```

需要保留的行为：

- provider registry 按 `model.api` 路由
- `stream` 和 `complete` 双入口
- 统一 event 协议
- provider 失败转成终态事件，而不是直接让 UI 崩掉

### `pimono.agent_core`

核心类型：

- `AgentMessage`
- `AgentState`
- `AgentTool`
- `AgentEvent`
- `AgentLoopConfig`

核心接口：

```python
class AgentTool(Protocol):
    name: str
    description: str
    parameters: dict[str, Any]

    async def execute(
        self,
        tool_call_id: str,
        args: dict[str, Any],
        signal: AbortSignal | None = None,
    ) -> Any: ...


class Agent(Protocol):
    async def prompt(self, message: AgentMessage | str) -> None: ...
    async def continue_(self) -> None: ...
    def abort(self) -> None: ...
    def subscribe(self, callback: Callable[[AgentEvent], None]) -> Callable[[], None]: ...
```

需要保留的行为：

- streaming turn 和 final turn 分离
- tool call 的顺序、校验和执行
- `sequential` / `parallel` 工具执行模式
- steering / follow-up 队列
- abort 和 continue 的语义

### `pimono.coding_agent`

核心类型：

- `SessionManager`
- `SettingsManager`
- `ModelRegistry`
- `ResourceLoader`
- `ExtensionRunner`
- `AgentSession`

核心接口建议：

```python
class SessionManager(Protocol):
    def append_message(self, message: AgentMessage) -> None: ...
    def get_entries(self) -> list[SessionEntry]: ...
    def build_context(self) -> list[Message]: ...


class SettingsManager(Protocol):
    def get_global_settings(self) -> Settings: ...
    def get_project_settings(self) -> Settings: ...
    def save(self) -> None: ...


class ResourceLoader(Protocol):
    async def load(self) -> ResourceLoadResult: ...


class ExtensionRunner(Protocol):
    async def emit(self, event: ExtensionEvent) -> None: ...
```

需要保留的行为：

- session tree / branch / compaction
- settings 全局 + 项目叠加
- model registry 的动态 provider 注入
- extension 的 before/after/hook 机制
- resource discovery 的冲突诊断

### `pimono.mom`

核心类型：

- `SlackEvent`
- `SlackContext`
- `ChannelStore`
- `MomRunner`
- `SandboxExecutor`

核心接口建议：

```python
class SlackTransport(Protocol):
    async def post_message(self, channel: str, text: str) -> str: ...
    async def update_message(self, channel: str, ts: str, text: str) -> None: ...
    async def delete_message(self, channel: str, ts: str) -> None: ...
    async def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str: ...


class WorkspaceStore(Protocol):
    def process_attachments(self, channel_id: str, files: list[SlackFile], ts: str) -> list[Attachment]: ...
    async def log_message(self, channel_id: str, message: LoggedMessage) -> bool: ...
```

需要保留的行为：

- channel 级独立目录
- `log.jsonl` 源事实
- `context` 由 `log.jsonl` 同步生成
- host / docker sandbox 切换
- 消息聚合和 main/thread 双输出

### `pimono.pods`

核心类型：

- `PodConfig`
- `PodRegistry`
- `ModelPlan`
- `RemoteExecutor`
- `VllmLauncher`
- `AgentCli`

核心接口建议：

```python
class RemoteExecutor(Protocol):
    async def exec(self, command: str, timeout: int | None = None) -> ExecResult: ...
    def get_workspace_path(self, host_path: str) -> str: ...


class VllmLauncher(Protocol):
    async def start(self, plan: ModelPlan) -> RunningModel: ...
    async def stop(self, name: str | None = None) -> None: ...
```

需要保留的行为：

- pod setup / list / active / remove
- model planning 与 GPU 规划
- OpenAI-compatible endpoint
- standalone agent CLI

### `pimono.web`

如果 Python 侧最终只提供后端服务，那么 `pimono.web` 主要承担协议和数据层，而不是前端渲染。

核心类型：

- `AppStorage`
- `SessionStore`
- `ProviderKeyStore`
- `CustomProviderStore`
- `Attachment`
- `Artifact`
- `MessageTransformer`

核心接口建议：

```python
class StorageBackend(Protocol):
    async def get(self, store: str, key: str) -> Any: ...
    async def set(self, store: str, key: str, value: Any) -> None: ...


class AttachmentLoader(Protocol):
    async def load(self, source: str | bytes | Path) -> AttachmentPayload: ...
```

需要保留的行为：

- session metadata 和 full session 分离
- provider key 与 proxy 设置分层
- attachment/document ingestion 独立
- artifact 作为可重放消息

## 4. 关键运行时边界

### 事件流边界

所有入口都应该共享一条事件语义：

- LLM stream event
- agent event
- session event
- UI event

不要把它们全部压成普通日志字符串，否则后面很难做回放和调试。

### 状态边界

建议把状态分成四类：

- ephemeral: 运行中的 stream / abort signal
- session: 当前对话上下文
- workspace: 可恢复的持久文件
- registry: provider / model / extension / tool 的发现结果

### 依赖边界

最重要的一条是：

- `pimono.agent_core` 只能依赖 `pimono.ai`
- `pimono.coding_agent` 依赖前两者
- `pimono.mom` / `pimono.pods` / `pimono.web` 都只能向下依赖，不要反向引用业务层

## 5. 行为兼容点清单

以下行为在 Python 版里建议优先保持：

- `AssistantMessageEvent` 的 start/delta/end/done/error 协议
- thinking / reasoning block 的增量处理
- tool call JSON 片段的流式拼装
- orphan tool call 的补偿逻辑
- parallel tool execution 的校验顺序
- session compaction 和 branch summary
- provider key 解析和 env fallback
- cross-provider replay / message normalization
- Slack / Web 的 attachment 作为多模态上下文
- artifact / session / storage 的持久化语义

## 6. 建议的实现顺序

1. 先做 `pimono.ai`
2. 再做 `pimono.agent_core`
3. 再做 `pimono.coding_agent`
4. 最后补 `mom`、`pods`、`web`

原因很简单：

- 上层入口都共享同一套流、消息、工具和 session 语义
- 先把协议层做稳，后面 UI / Slack / CLI 的适配成本会低很多

## 7. 可执行初始化骨架

### 7.1 最小可落地的 `src/` 骨架

如果现在就开始建 Python 工程，我建议先只落这几个目录和文件：

```text
src/pimono/
├── __init__.py
├── ai/
│   ├── __init__.py
│   ├── models.py
│   ├── messages.py
│   ├── events.py
│   ├── types.py
│   ├── stream.py
│   ├── registry.py
│   ├── replay.py
│   ├── validation.py
│   └── providers/
│       ├── __init__.py
│       ├── anthropic.py
│       ├── openai_completions.py
│       └── openai_responses.py
├── agent_core/
│   ├── __init__.py
│   ├── agent.py
│   ├── loop.py
│   ├── state.py
│   ├── tools.py
│   └── proxy.py
└── coding_agent/
    ├── __init__.py
    ├── sdk.py
    ├── session/
    ├── settings/
    ├── models/
    ├── resources/
    └── extensions/
```

这个骨架的目的不是一次做全，而是先把“未来依赖会落在哪些模块里”固定住。

### 7.2 `__init__.py` 导出约定

建议每层包的 `__init__.py` 只做两件事：

- 导出稳定公共 API
- 保持内部实现文件可替换

推荐导出策略：

- `pimono.ai.__init__`
  - `Model`
  - `Context`
  - `Message`
  - `AssistantMessage`
  - `AssistantMessageEvent`
  - `StreamOptions`
  - `Provider`
  - `AssistantMessageStream`
- `pimono.agent_core.__init__`
  - `Agent`
  - `AgentState`
  - `AgentEvent`
  - `AgentTool`
  - `AgentLoopConfig`
- `pimono.coding_agent.__init__`
  - `create_agent_session`
  - `SessionManager`
  - `SettingsManager`
  - `ModelRegistry`
  - `ResourceLoader`
  - `ExtensionRunner`

不要把 provider 实现、session 私有类型、资源发现细节全部从根包直接暴露出来。

### 7.3 首批文件职责

#### `pimono/ai/models.py`

只放模型元数据和成本配置：

- `Model`
- `CostProfile`
- `ProviderRef`

#### `pimono/ai/messages.py`

只放消息和 content block：

- `TextBlock`
- `ThinkingBlock`
- `ToolCallBlock`
- `ToolResultBlock`
- `UserMessage`
- `AssistantMessage`
- `ToolResultMessage`

#### `pimono/ai/events.py`

只放流式事件：

- `AssistantMessageEvent`
- `AssistantMessageEventType`
- `StreamState`

#### `pimono/ai/stream.py`

只放 stream 容器：

- `AssistantMessageStream`
- `EventStreamResult`
- `merge_streams()`

#### `pimono/ai/registry.py`

只放 provider registry：

- `ApiRegistry`
- `Provider`
- `register_provider()`
- `get_provider()`

#### `pimono/agent_core/agent.py`

只放 agent facade：

- `Agent`
- `AgentSubscription`
- `AgentAbortError`

#### `pimono/agent_core/loop.py`

只放循环逻辑：

- `run_agent_loop()`
- `run_agent_loop_continue()`
- `execute_tool_calls()`
- `prepare_tool_call()`

#### `pimono/coding_agent/sdk.py`

只放组装逻辑：

- `create_agent_session()`
- `build_default_context()`
- `create_default_tools()`

### 7.4 目录初始化顺序

推荐按这个顺序建文件：

1. 先建 `pimono/ai`
2. 再建 `pimono/agent_core`
3. 再建 `pimono/coding_agent/session` 和 `settings`
4. 再建 `models`、`resources`、`extensions`
5. 最后做 `mom`、`pods`、`web`

这样可以保证底层协议稳定，后面的包只是在拼装，不会反过来塑造基础抽象。

### 7.5 最小测试骨架

建议一开始就同步建测试目录：

```text
tests/
├── ai/
│   ├── test_models.py
│   ├── test_stream.py
│   └── test_registry.py
├── agent_core/
│   ├── test_loop.py
│   └── test_tools.py
└── coding_agent/
    ├── test_session_manager.py
    ├── test_settings_manager.py
    └── test_model_registry.py
```

优先写的测试不是 UI，而是：

- tool call 增量拼装
- provider registry 路由
- session append-only 语义
- compaction / branch summary 结构
- settings merge 和 fallback

### 7.6 最小依赖建议

第一阶段尽量少依赖：

- `pydantic` 或 `dataclasses`
- `httpx`
- `jsonschema`
- `python-slack-sdk` 仅在 `mom`
- `watchdog` 仅在 `mom` / `coding_agent`

先不要把渲染层、CLI shell 风格工具和 UI 库引入基础包。

## 8. 可执行包结构草案

这一节把目录结构再收敛成“可以直接开始建仓”的版本。目标是让第一版 Python 实现不被外围模块拖累。

### 8.1 第一阶段仓库形态

```text
pi-mono-py/
├── pyproject.toml
├── README.md
├── src/
│   └── pimono/
│       ├── __init__.py
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── messages.py
│       │   ├── events.py
│       │   ├── stream.py
│       │   ├── registry.py
│       │   └── providers/
│       ├── agent_core/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── loop.py
│       │   ├── state.py
│       │   └── proxy.py
│       ├── coding_agent/
│       │   ├── __init__.py
│       │   ├── sdk.py
│       │   ├── main.py
│       │   ├── session/
│       │   ├── settings/
│       │   ├── models/
│       │   ├── resources/
│       │   ├── extensions/
│       │   └── utils/
│       ├── ui/
│       │   ├── __init__.py
│       │   └── interactive/
│       ├── rpc/
│       │   ├── __init__.py
│       │   ├── server.py
│       │   ├── client.py
│       │   └── protocol.py
│       ├── mom/
│       ├── pods/
│       └── web/
└── tests/
    ├── ai/
    ├── agent_core/
    └── coding_agent/
```

### 8.2 实现顺序

建议按下面顺序落地：

1. `pimono.ai`
2. `pimono.agent_core`
3. `pimono.coding_agent.session`
4. `pimono.coding_agent.settings`
5. `pimono.coding_agent.models`
6. `pimono.coding_agent.resources`
7. `pimono.coding_agent.extensions`
8. `pimono.coding_agent.sdk`
9. `pimono.coding_agent.main`
10. `pimono.rpc`
11. `pimono.ui.interactive`
12. `pimono.mom`
13. `pimono.pods`
14. `pimono.web`

### 8.3 可执行入口

建议保留三个入口脚本：

- `pimono`：主 CLI
- `pimono-rpc`：RPC 宿主模式
- `pimono-ai`：协议层测试和 provider 调试

### 8.4 先建哪些文件

第一批建议只建这些文件：

- `src/pimono/ai/models.py`
- `src/pimono/ai/messages.py`
- `src/pimono/ai/events.py`
- `src/pimono/ai/stream.py`
- `src/pimono/agent_core/agent.py`
- `src/pimono/agent_core/loop.py`
- `src/pimono/coding_agent/session/manager.py`
- `src/pimono/coding_agent/settings/manager.py`
- `src/pimono/coding_agent/models/registry.py`
- `src/pimono/coding_agent/resources/loader.py`
- `src/pimono/coding_agent/extensions/runner.py`
- `src/pimono/coding_agent/sdk.py`

这些文件足够把核心链路跑通，其他模块可以后补。

### 8.5 包导出策略

- 公共 API 只从包根导出
- 子包内部类型不从根包导出
- provider 实现不向上层暴露
- session 私有协作者不进入公共命名空间

### 8.6 测试目录建议

```text
tests/
├── ai/
├── agent_core/
├── coding_agent/
├── rpc/
├── ui/
├── mom/
├── pods/
└── web/
```

### 8.7 为什么这个结构可执行

- 协议、状态机、产品层分开，依赖方向清晰
- 先建最小文件就能写测试
- 后续可以逐步补 UI 和外围产品，而不会重构根包
- 适合持续迭代，不要求第一天就把所有模块做完

## 9. 第一批初始化文件清单与导出约定

这部分把“先建哪些 `__init__.py`，每层包导出什么”收敛成一个更明确的初始化约定。

### 9.1 第一批初始化文件

优先初始化以下文件：

- `src/pimono/__init__.py`
- `src/pimono/ai/__init__.py`
- `src/pimono/ai/providers/__init__.py`
- `src/pimono/agent_core/__init__.py`
- `src/pimono/coding_agent/__init__.py`
- `src/pimono/coding_agent/session/__init__.py`
- `src/pimono/coding_agent/settings/__init__.py`
- `src/pimono/coding_agent/models/__init__.py`
- `src/pimono/coding_agent/resources/__init__.py`
- `src/pimono/coding_agent/extensions/__init__.py`
- `src/pimono/mom/__init__.py`
- `src/pimono/pods/__init__.py`
- `src/pimono/web/__init__.py`
- `src/pimono/rpc/__init__.py`
- `src/pimono/ui/__init__.py`

### 9.2 导出约定

- 顶层包 `pimono.__init__` 只导出最稳定的总入口，例如版本号、主 CLI 或少量聚合类型
- `pimono.ai` 只导出协议层公共类型，不导出 provider 内部实现
- `pimono.agent_core` 只导出 agent loop 的公共协议和 facade
- `pimono.coding_agent` 只导出产品层入口、manager 和 runtime facade
- 子包的 `__init__.py` 不承担复杂逻辑，只做 re-export
- 私有实现一律以下划线文件或内部类名承载，不进入公共 API

### 9.3 首批导出策略

建议首批导出采用“少而稳”的方式：

- `pimono.ai`
  - `Model`
  - `Message`
  - `Context`
  - `AssistantMessage`
  - `AssistantMessageEvent`
  - `Provider`
  - `AssistantMessageStream`
- `pimono.agent_core`
  - `Agent`
  - `AgentState`
  - `AgentEvent`
  - `AgentTool`
  - `AgentLoopConfig`
- `pimono.coding_agent`
  - `main`
  - `AgentSession`
  - `SessionManager`
  - `SettingsManager`
  - `ModelRegistry`
  - `ResourceLoader`
  - `ExtensionRunner`

### 9.4 初始化文件落地原则

- 先补 `__init__.py` 再补实现文件，避免导出表和实现文件不同步
- 每完成一个子包，都先补测试，再补更大范围的聚合导出
- 入口层的导出尽量保持稳定，不跟着内部重构频繁变动

### 9.5 `core` 稳定导出层约定

`pimono.coding_agent.core` 建议再拆一层 `public.py`，作为稳定导出层：

- `core/types.py` 只放共享 dataclass、Protocol 和类型别名
- `core/public.py` 只负责聚合公共 API
- `core/__init__.py` 只做转发，不写实现逻辑
- `core/internal.py` 专门收纳 `InMemory*` 这类实现辅助类型
- `core/memory.py` 放内存实现
- `core/helpers.py` 放内部 helper 函数
- 具体实现文件继续留在 `agent_session.py`、`session.py`、`settings.py` 等内部模块
- `InMemory*` 一类实现辅助类型不进入稳定导出面

这样做的好处是：

- 公共导入路径稳定
- 内部模块可以自由重构
- 测试可以继续直接引用内部实现，不影响外部 API 约定

### 9.7 三层拆分的实际落地顺序

建议按这个顺序推进：

1. 先把 `types.py` 建立成唯一的共享类型源
2. 再按领域拆出 `session_types.py`、`runtime_types.py`、`resource_types.py`
3. 再把 `public.py` 切到这些细分类型层
4. 再把 `internal.py` 拆成 `memory.py` 和 `helpers.py`
5. 最后逐个把实现模块的重复类型定义收掉

这样可以先稳定外部 API，再慢慢消除内部重复定义。

### 9.8 `session.py` 的三段式拆分

`session.py` 的业务逻辑现在建议再分成三个可单测模块：

- `reader.py`
  - 负责 session 加载、上下文组装、统计和信息摘要
- `writer.py`
  - 负责 append、flush、close、JSONL 写入
- `tree.py`
  - 负责 branch、fork、tree 构建、leaf/child 查询

`session.py` 本体只保留 `InMemorySessionManager` 这个薄壳，方法体优先转发到上述三个模块。

### 9.6 mode 统一参数与返回码约定

`pimono` 的三种 mode 建议共享一套解析层：

- `modes/shared.py` 提供统一 `ModeInvocation`
- `modes/shared.py` 提供统一退出码枚举 `ModeExitCode`
- `cli/main.py` 只做 mode 分发，不重复写参数解析
- `interactive`、`print`、`rpc` 三个 mode 的 `run()` 都返回整数退出码

推荐的退出码约定：

- `0`: 成功完成
- `1`: 运行时错误
- `2`: 参数错误或无效输入
