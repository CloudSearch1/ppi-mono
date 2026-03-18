# Python 包结构图

这份文档把 `pi-coding-agent` 的重写边界收敛成 5 个主包：

- `pi_core`
- `pi_session`
- `pi_resources`
- `pi_extensions`
- `pi_cli`

目标是让每个包只负责一类稳定语义，避免 Python 重写时把 UI、会话、模型、扩展、资源发现揉成一团。

---

## 1. 总体分层

```text
pi-mono-py/
└── src/
    └── pimono/
        ├── pi_core/
        ├── pi_session/
        ├── pi_resources/
        ├── pi_extensions/
        ├── pi_cli/
        └── shared/
```

推荐依赖方向：

```text
pi_cli -> pi_extensions -> pi_resources -> pi_session -> pi_core
                         \-> shared
pi_session -> pi_core
pi_resources -> shared
pi_extensions -> pi_core + shared
```

核心原则：

- `pi_core` 只管 LLM / agent runtime 语义
- `pi_session` 只管 session tree、branch、compaction、fork
- `pi_resources` 只管 skills / prompts / themes / AGENTS / SYSTEM 发现
- `pi_extensions` 只管插件、命令、工具、hook、UI 扩展点
- `pi_cli` 只管入口、模式分发、交互命令

---

## 2. 推荐目录树

```text
src/pimono/
├── __init__.py
├── shared/
│   ├── __init__.py
│   ├── types.py
│   ├── events.py
│   ├── ids.py
│   ├── errors.py
│   └── utils.py
├── pi_core/
│   ├── __init__.py
│   ├── agent.py
│   ├── loop.py
│   ├── state.py
│   ├── messages.py
│   ├── tools.py
│   ├── transport.py
│   ├── proxy.py
│   └── compatibility.py
├── pi_session/
│   ├── __init__.py
│   ├── manager.py
│   ├── tree.py
│   ├── entries.py
│   ├── compaction.py
│   ├── branch.py
│   ├── fork.py
│   ├── storage.py
│   └── migrations.py
├── pi_resources/
│   ├── __init__.py
│   ├── loader.py
│   ├── discovery.py
│   ├── diagnostics.py
│   ├── prompts.py
│   ├── skills.py
│   ├── themes.py
│   └── package_sources.py
├── pi_extensions/
│   ├── __init__.py
│   ├── runner.py
│   ├── registry.py
│   ├── loader.py
│   ├── types.py
│   ├── context.py
│   └── wrappers.py
└── pi_cli/
    ├── __init__.py
    ├── main.py
    ├── args.py
    ├── modes/
    │   ├── __init__.py
    │   ├── interactive.py
    │   ├── print.py
    │   └── rpc.py
    ├── commands/
    │   ├── __init__.py
    │   ├── package.py
    │   ├── config.py
    │   ├── session.py
    │   └── model.py
    └── ui/
        ├── __init__.py
        ├── textual_app.py
        ├── prompt_toolkit_editor.py
        └── overlays.py
```

---

## 3. 包职责图

### `pi_core`

职责：

- agent 状态机
- streaming loop
- tool call 生命周期
- transport abstraction
- message conversion
- proxy backend

建议包含的对象：

- `Agent`
- `AgentState`
- `AgentEvent`
- `AgentTool`
- `StreamFn`
- `AgentLoopConfig`

### `pi_session`

职责：

- JSONL session tree
- append-only history
- branch / fork / resume
- compaction / branch summary
- labels / metadata
- session migrations

建议包含的对象：

- `SessionManager`
- `SessionEntry`
- `SessionHeader`
- `SessionTreeNode`
- `CompactionEntry`
- `BranchSummaryEntry`

### `pi_resources`

职责：

- 发现项目和全局资源
- 合并资源来源
- 冲突诊断
- context file 读取
- package source 解析

建议包含的对象：

- `ResourceLoader`
- `ResourceDiagnostic`
- `PromptTemplate`
- `Skill`
- `Theme`

### `pi_extensions`

职责：

- extension loader / runner
- 注册 tool / command / flag / shortcut
- session / provider / UI hooks
- tool wrapper
- custom runtime context

建议包含的对象：

- `ExtensionRunner`
- `ExtensionAPI`
- `ExtensionEvent`
- `ExtensionContext`
- `ExtensionUIContext`
- `RegisteredTool`

### `pi_cli`

职责：

- 参数解析
- interactive / print / rpc 分发
- session picker / model picker / config UI
- package command
- 入口 wiring

建议包含的对象：

- `main()`
- `parse_args()`
- `run_interactive()`
- `run_print()`
- `run_rpc()`

---

## 4. 包内接口草图

### `pi_core`

```python
class Agent(Protocol):
    async def prompt(self, message: AgentMessage | str) -> None: ...
    async def continue_(self) -> None: ...
    def abort(self) -> None: ...
    def subscribe(self, callback: Callable[[AgentEvent], None]) -> Callable[[], None]: ...
```

### `pi_session`

```python
class SessionManager(Protocol):
    def append_message(self, message: AgentMessage) -> str: ...
    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int) -> str: ...
    def build_context(self) -> SessionContext: ...
    def branch(self, entry_id: str) -> None: ...
    def create_branched_session(self, leaf_id: str) -> str | None: ...
```

### `pi_resources`

```python
class ResourceLoader(Protocol):
    async def reload(self) -> None: ...
    def get_extensions(self) -> ExtensionLoadResult: ...
    def get_skills(self) -> list[Skill]: ...
    def get_prompts(self) -> list[PromptTemplate]: ...
    def get_themes(self) -> list[Theme]: ...
```

### `pi_extensions`

```python
class ExtensionRunner(Protocol):
    async def emit(self, event: ExtensionEvent) -> Any: ...
    def get_command(self, name: str) -> RegisteredCommand | None: ...
    def get_all_registered_tools(self) -> list[RegisteredTool]: ...
```

### `pi_cli`

```python
def main(argv: list[str]) -> int: ...
def parse_args(argv: list[str]) -> Args: ...
def create_session(options: CreateAgentSessionOptions) -> AgentSession: ...
```

---

## 5. 依赖约束

### 允许

- `pi_cli` 依赖所有其他包
- `pi_extensions` 依赖 `pi_core`
- `pi_session` 依赖 `pi_core`
- `pi_resources` 可以依赖 `shared`

### 不建议

- `pi_core` 反向依赖 `pi_cli`
- `pi_session` 直接调用 TUI 或 Web UI
- `pi_extensions` 直接操作文件系统 UI 组件
- `pi_resources` 直接保存 session 状态

这四条如果破了，后面会很难把 TUI / Web / RPC 共用起来。

---

## 6. Python 选型建议

### `pi_core`

优先：

- `pydantic`
- `asyncio`
- `httpx`
- `anyio`

### `pi_session`

优先：

- JSONL
- `pathlib`
- `filelock`
- `sqlite3` 作为后续升级选项

### `pi_resources`

优先：

- `pathlib`
- `tomllib` / `yaml`
- `watchdog` 或文件轮询

### `pi_extensions`

优先：

- `importlib`
- `entry_points`
- `pluggy` 或轻量自定义注册表

### `pi_cli`

优先：

- `typer`
- `rich`
- `textual`
- `prompt_toolkit`

---

## 7. 最小可行实现顺序

1. `pi_core`
2. `pi_session`
3. `pi_resources`
4. `pi_extensions`
5. `pi_cli`

如果只能先做一条链路，建议先做：

```text
pi_cli -> pi_session -> pi_core
```

因为这条链路已经能跑起最小交互、session 保存和模型调用。
