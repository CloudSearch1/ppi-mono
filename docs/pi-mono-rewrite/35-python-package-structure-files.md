# Python 包目录骨架与文件清单

这份文档把前面的 Python 包结构进一步落到“目录 + 文件”的粒度，方便直接开工。

目标是：

- 先固定模块边界
- 再固定每个文件的大致职责
- 最后让后续实现尽量按文件推进，而不是按“巨型模块”推进

---

## 1. 总体目录

```text
pi-mono-py/
├── pyproject.toml
├── README.md
├── tests/
└── src/
    └── pimono/
        ├── shared/
        ├── pi_core/
        ├── pi_session/
        ├── pi_resources/
        ├── pi_extensions/
        ├── pi_cli/
        ├── mom_core/
        ├── mom_platforms/
        ├── mom_storage/
        ├── mom_scheduler/
        ├── mom_sandbox/
        ├── pods_cli/
        ├── pods_store/
        ├── pods_ssh/
        ├── pods_setup/
        ├── pods_models/
        └── pods_runtime/
```

推荐依赖方向：

```text
pi_cli -> pi_extensions -> pi_resources -> pi_session -> pi_core
mom_* -> pi_core + pi_session + pi_resources
pods_* -> shared + external shell/ssh libs
```

---

## 2. `shared` 文件清单

### 目录

```text
src/pimono/shared/
├── __init__.py
├── types.py
├── events.py
├── ids.py
├── errors.py
└── utils.py
```

### 文件职责

- `types.py`
  - `Usage`
  - `ModelRef`
  - `TextContent`
  - `ImageContent`
  - `ToolCall`
  - `ToolResult`
- `events.py`
  - 通用事件基础类
  - JSONL 序列化/反序列化辅助
- `ids.py`
  - UUID / short id / session id 生成
- `errors.py`
  - 统一错误结构
- `utils.py`
  - 字符串、路径、时间、JSON helper

---

## 3. `pi_core` 文件清单

### 目录

```text
src/pimono/pi_core/
├── __init__.py
├── agent.py
├── loop.py
├── state.py
├── messages.py
├── tools.py
├── transport.py
├── proxy.py
└── compatibility.py
```

### 文件职责

- `agent.py`
  - `Agent` 实现
  - prompt / continue / abort / subscribe
- `loop.py`
  - agent loop orchestration
  - tool preflight / execution / postprocess
- `state.py`
  - `AgentState`
  - streaming state / queue state
- `messages.py`
  - `AgentMessage` 相关 dataclass
  - custom message normalization
- `tools.py`
  - `Tool` / `AgentTool`
  - tool schema 与工具注册
- `transport.py`
  - provider transport protocol
  - SSE/WebSocket/HTTP adapters
- `proxy.py`
  - 代理转发实现
- `compatibility.py`
  - provider 差异适配
  - thinking / reasoning / tool-call 兼容开关

---

## 4. `pi_session` 文件清单

### 目录

```text
src/pimono/pi_session/
├── __init__.py
├── manager.py
├── tree.py
├── entries.py
├── compaction.py
├── branch.py
├── fork.py
├── storage.py
└── migrations.py
```

### 文件职责

- `manager.py`
  - `SessionManager`
  - 对外会话仓储入口
- `tree.py`
  - `SessionTreeNode`
  - `build_tree()`
- `entries.py`
  - `SessionHeader`
  - `SessionMessageEntry`
  - `CompactionEntry`
  - `BranchSummaryEntry`
  - `CustomEntry`
  - `CustomMessageEntry`
- `compaction.py`
  - compaction strategy
  - branch summary generation
- `branch.py`
  - branch / label / leaf pointer
- `fork.py`
  - fork session / clone branch
- `storage.py`
  - JSONL file I/O
  - lock / append / replay
- `migrations.py`
  - session format migration
  - backward compatibility

---

## 5. `pi_resources` 文件清单

### 目录

```text
src/pimono/pi_resources/
├── __init__.py
├── loader.py
├── discovery.py
├── diagnostics.py
├── prompts.py
├── skills.py
├── themes.py
└── package_sources.py
```

### 文件职责

- `loader.py`
  - resource aggregation
  - reload lifecycle
- `discovery.py`
  - filesystem scanning
  - AGENTS / SYSTEM discovery
- `diagnostics.py`
  - collisions / parse errors / warnings
- `prompts.py`
  - prompt template loading
- `skills.py`
  - skill loading
- `themes.py`
  - theme loading
- `package_sources.py`
  - package source manifest parsing

---

## 6. `pi_extensions` 文件清单

### 目录

```text
src/pimono/pi_extensions/
├── __init__.py
├── runner.py
├── registry.py
├── loader.py
├── types.py
├── context.py
└── wrappers.py
```

### 文件职责

- `runner.py`
  - extension lifecycle
  - event dispatch
- `registry.py`
  - command / tool / shortcut / flag registry
- `loader.py`
  - extension discovery / import / hot reload
- `types.py`
  - extension event / API / config types
- `context.py`
  - UI context / command context / session context exposed to extensions
- `wrappers.py`
  - wrap extension tools for agent runtime

---

## 7. `pi_cli` 文件清单

### 目录

```text
src/pimono/pi_cli/
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

### 文件职责

- `main.py`
  - program entry
  - mode dispatch
  - session factory wiring
- `args.py`
  - CLI schema / parsing
- `modes/interactive.py`
  - interactive shell loop
- `modes/print.py`
  - single-shot output
- `modes/rpc.py`
  - JSONL stdin/stdout protocol
- `commands/package.py`
  - install / remove / update / list
- `commands/config.py`
  - resource enable/disable UI
- `commands/session.py`
  - resume / fork / tree / export
- `commands/model.py`
  - model selection / provider auth
- `ui/textual_app.py`
  - TUI shell
- `ui/prompt_toolkit_editor.py`
  - high fidelity editor
- `ui/overlays.py`
  - overlay / modal / picker helpers

---

## 8. `mom` 文件清单

### 目录

```text
src/pimono/mom_core/
├── __init__.py
├── runner.py
├── prompt.py
├── tools.py
├── memory.py
└── context_sync.py

src/pimono/mom_platforms/
├── __init__.py
└── slack/
    ├── __init__.py
    ├── adapter.py
    ├── events.py
    ├── formatting.py
    └── client.py

src/pimono/mom_storage/
├── __init__.py
├── channel_store.py
├── log_store.py
├── context_store.py
└── attachments.py

src/pimono/mom_scheduler/
├── __init__.py
├── watcher.py
├── event_types.py
└── cron.py

src/pimono/mom_sandbox/
├── __init__.py
├── executor.py
├── docker_executor.py
└── host_executor.py
```

### 文件职责

- `mom_core/runner.py`
  - per-channel agent orchestration
- `mom_core/prompt.py`
  - system prompt assembly
- `mom_core/tools.py`
  - mom tools
- `mom_core/memory.py`
  - MEMORY.md loading and merging
- `mom_core/context_sync.py`
  - log.jsonl -> context sync
- `mom_platforms/slack/adapter.py`
  - Slack event bridge
- `mom_platforms/slack/events.py`
  - Slack event normalization
- `mom_platforms/slack/formatting.py`
  - Slack mrkdwn formatting
- `mom_platforms/slack/client.py`
  - Web API wrapper
- `mom_storage/channel_store.py`
  - per-channel filesystem state
- `mom_storage/log_store.py`
  - log.jsonl source of truth
- `mom_storage/context_store.py`
  - context.jsonl management
- `mom_storage/attachments.py`
  - downloads / file mapping
- `mom_scheduler/watcher.py`
  - events directory watcher
- `mom_scheduler/event_types.py`
  - immediate / one-shot / periodic
- `mom_scheduler/cron.py`
  - cron trigger resolution
- `mom_sandbox/executor.py`
  - sandbox abstraction
- `mom_sandbox/docker_executor.py`
  - Docker implementation
- `mom_sandbox/host_executor.py`
  - host implementation

---

## 9. `pods` 文件清单

### 目录

```text
src/pimono/pods_cli/
├── __init__.py
├── main.py
├── args.py
└── commands/
    ├── __init__.py
    ├── pods.py
    ├── models.py
    ├── prompt.py
    ├── ssh.py
    └── agent.py

src/pimono/pods_store/
├── __init__.py
├── config.py
├── config_io.py
└── validation.py

src/pimono/pods_ssh/
├── __init__.py
├── exec.py
├── stream.py
└── scp.py

src/pimono/pods_setup/
├── __init__.py
├── bootstrap.py
├── templates.py
└── remote_state.py

src/pimono/pods_models/
├── __init__.py
├── registry.py
├── configs.py
├── compatibility.py
└── discovery.py

src/pimono/pods_runtime/
├── __init__.py
├── manager.py
├── process.py
├── logs.py
└── api.py
```

### 文件职责

- `pods_cli/main.py`
  - top-level CLI entry
- `pods_cli/commands/pods.py`
  - pod setup / list / active / remove
- `pods_cli/commands/models.py`
  - model start / stop / logs / list
- `pods_cli/commands/prompt.py`
  - standalone agent / prompt commands
- `pods_cli/commands/ssh.py`
  - shell and remote ssh commands
- `pods_cli/commands/agent.py`
  - interactive agent wrapper
- `pods_store/config.py`
  - local pod config model
- `pods_store/config_io.py`
  - persist config to disk
- `pods_store/validation.py`
  - config validation and migration
- `pods_ssh/exec.py`
  - ssh command execution
- `pods_ssh/stream.py`
  - streaming stdout/stderr
- `pods_ssh/scp.py`
  - file copy to remote
- `pods_setup/bootstrap.py`
  - remote setup scripts
- `pods_setup/templates.py`
  - script templates
- `pods_setup/remote_state.py`
  - remote path / pid / log conventions
- `pods_models/registry.py`
  - known model registry
- `pods_models/configs.py`
  - model config resolution
- `pods_models/compatibility.py`
  - GPU / vLLM compatibility checks
- `pods_models/discovery.py`
  - detect local / remote model state
- `pods_runtime/manager.py`
  - start / stop / list orchestration
- `pods_runtime/process.py`
  - remote PID and process lifecycle
- `pods_runtime/logs.py`
  - log tailing and parsing
- `pods_runtime/api.py`
  - OpenAI-compatible endpoint metadata

---

## 10. 实现顺序建议

### 第一阶段

```text
shared -> pi_core -> pi_session -> pi_resources -> pi_extensions -> pi_cli
```

### 第二阶段

```text
mom_storage -> mom_platforms/slack -> mom_core -> mom_sandbox -> mom_scheduler
```

### 第三阶段

```text
pods_store -> pods_ssh -> pods_models -> pods_setup -> pods_runtime -> pods_cli
```

---

## 11. 重点保留的接口边界

- `pi_core` 的消息 / 事件 / transport 边界
- `pi_session` 的 append-only tree 边界
- `mom` 的 channel-isolated store 边界
- `pods` 的 local-config vs remote-process 边界

只要这四层边界清晰，后续 UI、协议、脚本都可以替换。
