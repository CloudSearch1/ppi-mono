# Python 重写接口规范与迁移步骤

本文档把 `pi-mono` 的重写工作收敛成接口定义、数据模型和迁移顺序，目标是让 Python 版可逐步替换 TypeScript 版，而不是一次性重写。

## 1. 核心接口规范

### `Model`

```python
@dataclass
class Model:
    provider: str
    api: str
    id: str
    base_url: str | None = None
    reasoning: bool = False
    context_window: int | None = None
    max_tokens: int | None = None
    cost: CostProfile | None = None
    compat: dict[str, Any] | None = None
```

### `Context`

```python
@dataclass
class Context:
    system_prompt: str | None
    messages: list[Message]
    tools: list[Tool]
```

### `AgentMessage`

最低要支持：

- `user`
- `assistant`
- `toolResult`
- `custom`
- `bashExecution`
- `branchSummary`
- `compactionSummary`
- `user-with-attachments`
- `artifact`

### `AssistantMessage`

必须能表达：

- text block
- thinking block
- tool call block
- stop reason
- usage
- error message
- response id

### `SessionEntry`

```python
@dataclass
class SessionEntry:
    id: str
    parent_id: str | None
    timestamp: str
    type: str
```

具体 entry 类型：

- `message`
- `thinking_level_change`
- `model_change`
- `compaction`
- `branch_summary`
- `custom`
- `custom_message`
- `label`
- `session_info`

### `Attachment`

```python
@dataclass
class Attachment:
    id: str
    type: Literal["image", "document"]
    file_name: str
    mime_type: str
    size: int
    content: str
    extracted_text: str | None = None
    preview: str | None = None
```

### `StorageBackend`

必须支持：

- `get`
- `set`
- `delete`
- `keys`
- `get_all_from_index`
- `clear`
- `has`
- `transaction`
- `get_quota_info`
- `request_persistence`

## 1.1 `SessionManager` 细化接口

```python
class SessionManager:
    # --- Construction ---
    @classmethod
    def create(
        cls,
        cwd: str,
        session_dir: str,
        *,
        persist: bool = True,
        session_id: str | None = None,
        parent_session: str | None = None,
    ) -> "SessionManager": ...

    @classmethod
    def open(cls, session_file: str, session_dir: str | None = None) -> "SessionManager": ...
    @classmethod
    def continue_recent(cls, session_dir: str, cwd: str) -> "SessionManager": ...
    @classmethod
    def fork_from(cls, source_session_file: str, target_cwd: str, session_dir: str | None = None) -> "SessionManager": ...
    @classmethod
    def in_memory(cls, cwd: str = ".") -> "SessionManager": ...

    # --- Append-only writes ---
    def append_message(self, message: AgentMessage) -> str: ...
    def append_thinking_level_change(self, level: str) -> str: ...
    def append_model_change(self, provider: str, model_id: str) -> str: ...
    def append_compaction(self, summary: str, first_kept_entry_id: str, tokens_before: int, details: dict[str, Any] | None = None, from_hook: bool | None = None) -> str: ...
    def append_branch_summary(self, from_id: str, summary: str, details: dict[str, Any] | None = None, from_hook: bool | None = None) -> str: ...
    def append_custom_entry(self, custom_type: str, data: Any = None) -> str: ...
    def append_custom_message_entry(self, custom_type: str, content: Any, display: bool, details: Any = None) -> str: ...
    def append_label_change(self, target_id: str, label: str | None) -> str: ...
    def append_session_info(self, name: str) -> str: ...

    # --- Read/query ---
    def get_header(self) -> SessionHeader | None: ...
    def get_entries(self) -> list[SessionEntry]: ...
    def get_tree(self) -> list[SessionTreeNode]: ...
    def get_branch(self, from_id: str | None = None) -> list[SessionEntry]: ...
    def get_leaf_id(self) -> str | None: ...
    def get_leaf_entry(self) -> SessionEntry | None: ...
    def get_entry(self, entry_id: str) -> SessionEntry | None: ...
    def get_children(self, parent_id: str) -> list[SessionEntry]: ...
    def get_session_name(self) -> str | None: ...
    def get_session_stats(self) -> SessionStats: ...
    def build_session_context(self) -> SessionContext: ...

    # --- Branching / navigation ---
    def branch(self, branch_from_id: str | None) -> str: ...
    def branch_with_summary(self, branch_from_id: str | None, summary: str, details: Any | None = None, from_hook: bool = False) -> str: ...
    def reset_leaf(self, new_leaf_id: str | None) -> None: ...
    def create_branched_session(self, branch_from_id: str | None) -> "SessionManager": ...

    # --- Mutations to metadata ---
    def set_session_name(self, name: str) -> None: ...
    def set_label(self, entry_id: str, label: str | None) -> None: ...

    # --- Persistence ---
    def reload(self) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
```

### `SessionManager` 设计约束

- 所有 `append_*` 都必须返回新 entry id
- `append_message()` 不允许直接写 `compactionSummary` / `branchSummary`，这两类应使用专门 API
- `get_entries()` 返回的是可遍历线性历史，`get_tree()` 返回完整树
- `build_session_context()` 必须屏蔽掉 `custom`、`label`、`session_info`
- session 文件结构要保证向后兼容，迁移逻辑应独立到 migration 层

## 1.3 读写流程

### 1.3.1 启动加载

```text
SessionManager.open(path)
  -> read file content
  -> parse JSONL lines
  -> locate session header
  -> migrate to CURRENT_SESSION_VERSION if needed
  -> rebuild in-memory index
  -> set leaf pointer to last entry
```

### 1.3.2 新建 session

```text
SessionManager.create(...)
  -> create header
  -> initialize empty entry list
  -> set leaf = null
  -> optionally persist header immediately
```

### 1.3.3 追加 entry

```text
append_xxx()
  -> build typed entry object
  -> assign id / parent_id / timestamp
  -> push to in-memory list
  -> update by-id index
  -> move leaf pointer
  -> append JSON line if persistence enabled
```

### 1.3.4 fork / branch

```text
fork_from(source)
  -> read source JSONL
  -> copy header + entries into new file
  -> update parentSession
  -> rebuild indexes
  -> start new session id

branch(entry_id)
  -> just move leaf pointer
  -> next append creates a new child
```

### 1.3.5 reload / recover

```text
reload()
  -> re-read file
  -> re-run migration
  -> rebuild index and label map
  -> keep leaf at last valid entry
```

## 1.4 序列化 schema 示例

### 1.4.1 header

```json
{"type":"session","version":3,"id":"4d1b...","timestamp":"2026-03-18T12:00:00.000Z","cwd":"M:\\AI Agent\\ppi-mono","parentSession":null}
```

### 1.4.2 user message

```json
{"type":"message","id":"1","parentId":null,"timestamp":"2026-03-18T12:00:01.000Z","message":{"role":"user","content":"read README.md"}}
```

### 1.4.3 assistant message with tool call

```json
{"type":"message","id":"2","parentId":"1","timestamp":"2026-03-18T12:00:02.000Z","message":{"role":"assistant","content":[{"type":"text","text":"I'll inspect the file."},{"type":"toolCall","id":"call_1","name":"read","arguments":{"path":"README.md"}}],"provider":"anthropic","model":"claude-sonnet-4-20250514"}}
```

### 1.4.4 tool result

```json
{"type":"message","id":"3","parentId":"2","timestamp":"2026-03-18T12:00:03.000Z","message":{"role":"toolResult","toolCallId":"call_1","toolName":"read","content":[{"type":"text","text":"# project README"}],"isError":false}}
```

### 1.4.5 compaction

```json
{"type":"compaction","id":"9","parentId":"8","timestamp":"2026-03-18T12:10:00.000Z","summary":"Compressed earlier discussion and file edits.","firstKeptEntryId":"6","tokensBefore":48721,"details":{"readFiles":["README.md"],"modifiedFiles":["src/main.py"]},"fromHook":false}
```

### 1.4.6 branch summary

```json
{"type":"branch_summary","id":"10","parentId":"9","timestamp":"2026-03-18T12:11:00.000Z","fromId":"8","summary":"User explored an alternative implementation path.","details":{"readFiles":["docs/design.md"],"modifiedFiles":[]},"fromHook":false}
```

### 1.4.7 label / session info / custom message

```json
{"type":"label","id":"11","parentId":"10","timestamp":"2026-03-18T12:12:00.000Z","targetId":"2","label":"start-here"}
{"type":"session_info","id":"12","parentId":"11","timestamp":"2026-03-18T12:13:00.000Z","name":"rewrite-experiment"}
{"type":"custom_message","id":"13","parentId":"12","timestamp":"2026-03-18T12:14:00.000Z","customType":"extension-note","content":"Remember to update docs.","display":true,"details":{"source":"extension"}}
```

### 1.4.8 migration rules

#### v1 -> v2

- 补 `id`
- 补 `parentId`
- 把 `compaction.firstKeptEntryIndex` 改成 `firstKeptEntryId`

#### v2 -> v3

- header.version 改为 `3`
- `message.message.role == "hookMessage"` 的消息改为 `custom`

#### 迁移约束

- 迁移必须原地执行在内存 entry 列表上
- 迁移后写回整个文件，而不是只 patch 局部行
- 如果 header 缺失或文件损坏，应重建新 session 而不是继续 append

## 1.2 JSONL 文件格式

### 1.2.1 文件头

每个 session 文件第一行必须是 header：

```json
{"type":"session","version":3,"id":"...","timestamp":"...","cwd":"...","parentSession":"..."}
```

字段含义：

- `version`
  - 当前固定为 `3`
- `id`
  - session 文件唯一 ID
- `timestamp`
  - session 创建时间
- `cwd`
  - session 启动目录
- `parentSession`
  - fork 来源文件路径，可为空

### 1.2.2 追加式 entry

后续每行是一个 entry，统一使用：

- `id`
- `parentId`
- `timestamp`
- `type`

树结构依赖 `parentId`，不能通过行号推断。

### 1.2.3 entry 类型语义

| type | 作用 | 是否进入 LLM 上下文 |
|---|---|---|
| `message` | user / assistant / tool / bash 消息 | 是 |
| `thinking_level_change` | 记录 thinking 级别变化 | 否 |
| `model_change` | 记录模型变化 | 否 |
| `compaction` | 压缩摘要节点 | 是 |
| `branch_summary` | 分支摘要节点 | 是 |
| `custom` | 扩展状态持久化 | 否 |
| `custom_message` | 扩展注入消息 | 是 |
| `label` | 书签/标记 | 否 |
| `session_info` | 会话元数据 | 否 |

### 1.2.4 约束

- `message` 不能直接承载 compaction / branch summary 语义，这两类必须使用专用 entry
- `label` 是独立 entry，不是 session 元数据字段
- `custom` 和 `custom_message` 的区分要保持：
  - `custom` = 只给扩展读写
  - `custom_message` = 给扩展和 LLM 都可见
- migration 只负责“旧格式 -> 新格式”，不负责业务语义修正

## 2. 时序规范

### A. 用户发送消息

```text
User -> UI/CLI -> AgentSession.prompt()
  -> build message / attachments / prompt templates
  -> Agent.prompt()
  -> stream events
  -> persist message
  -> update UI / logs
```

### B. 工具调用

```text
assistant message contains toolCall
  -> beforeToolCall
  -> validate args
  -> execute tool
  -> afterToolCall
  -> append toolResult
  -> continue turn if needed
```

### C. Compaction

```text
context near limit
  -> auto compaction start
  -> summarize abandoned branch
  -> append compaction summary entry
  -> rebuild session context
  -> retry prompt
```

### D. Fork / Tree

```text
user chooses older entry
  -> branch or fork
  -> optionally summarize abandoned path
  -> update leaf pointer or new session file
  -> reload messages into agent
```

### E. Slack / Browser UI

```text
platform event or browser submit
  -> adapter / UI layer
  -> session prompt
  -> streaming state updates
  -> final response render
```

## 3. `ExtensionAPI` 细化接口

### 3.1 运行时对象

```python
class ExtensionAPI(Protocol):
    # Event subscription
    def on(self, event_name: str, handler: Callable[..., Any]) -> None: ...

    # Registration
    def register_tool(self, tool: ToolDefinition) -> None: ...
    def register_command(self, command: RegisteredCommand) -> None: ...
    def register_shortcut(self, shortcut: str, handler: Callable[..., Any]) -> None: ...
    def register_flag(self, flag: ExtensionFlag) -> None: ...
    def register_message_renderer(self, renderer: MessageRenderer) -> None: ...
    def register_provider(self, name: str, config: ProviderConfig) -> None: ...

    # Session / prompt actions
    def send_message(self, message: Any) -> None: ...
    def send_user_message(self, content: str) -> None: ...
    def append_entry(self, entry: Any) -> str: ...
    def set_session_name(self, name: str) -> None: ...
    def get_session_name(self) -> str | None: ...
    def set_label(self, entry_id: str, label: str | None) -> None: ...

    # Model / tools
    def get_active_tools(self) -> list[str]: ...
    def get_all_tools(self) -> list[ToolInfo]: ...
    def set_active_tools(self, tool_names: list[str]) -> None: ...
    def refresh_tools(self) -> None: ...
    def get_commands(self) -> list[SlashCommandInfo]: ...
    def set_model(self, model: Model) -> bool: ...
    def get_thinking_level(self) -> str: ...
    def set_thinking_level(self, level: str) -> None: ...

    # Environment / control
    def get_model(self) -> Model | None: ...
    def is_idle(self) -> bool: ...
    def abort(self) -> None: ...
    def has_pending_messages(self) -> bool: ...
    def shutdown(self) -> None: ...
    def get_context_usage(self) -> ContextUsage | None: ...
    def compact(self, options: CompactOptions | None = None) -> None: ...
    def get_system_prompt(self) -> str: ...

    # UI
    @property
    def ui(self) -> ExtensionUIContext: ...
```

### 3.2 Command context

```python
class ExtensionCommandContext(ExtensionContext, Protocol):
    def wait_for_idle(self) -> None: ...
    def new_session(
        self,
        *,
        parent_session: str | None = None,
        setup: Callable[[SessionManager], Any] | None = None,
    ) -> None: ...
    def fork(self, entry_id: str) -> None: ...
    def navigate_tree(self, entry_id: str) -> None: ...
    def switch_session(self, session_file: str) -> None: ...
    def reload(self) -> None: ...
```

### 3.3 Extension runtime state

```python
@dataclass
class ExtensionRuntimeState:
    flag_values: dict[str, bool | str] = field(default_factory=dict)
    pending_provider_registrations: list[tuple[str, ProviderConfig]] = field(default_factory=list)
```

### 3.4 事件表

建议将事件分成三层：

1. lifecycle events
2. prompt / tool / model events
3. session / tree / compaction events

#### 3.4.1 生命周期事件

| event | 作用 | handler 返回值 |
|---|---|---|
| `session_start` | 会话启动完成 | 无 |
| `session_before_switch` | 切 session 前拦截 | `cancel: bool` |
| `session_switch` | 切 session 后通知 | 无 |
| `session_before_fork` | fork 前拦截 | `cancel: bool`, `skipConversationRestore: bool` |
| `session_fork` | fork 后通知 | 无 |
| `session_before_compact` | compaction 前拦截 | `cancel: bool`, `compaction?: CompactionResult` |
| `session_compact` | compaction 后通知 | 无 |
| `session_shutdown` | 关闭前通知 | 无 |
| `session_before_tree` | tree 导航前拦截 | `cancel: bool`, `summary?: {...}` |
| `session_tree` | tree 导航后通知 | 无 |

#### 3.4.2 prompt / model / context 事件

| event | 作用 | handler 返回值 |
|---|---|---|
| `input` | 用户输入进入处理前 | `continue` / `handled` / `transform` |
| `before_agent_start` | prompt 进入 agent loop 前 | `message?`, `systemPrompt?` |
| `before_provider_request` | 请求 provider 前可替换 payload | 任意 payload |
| `context` | 每轮 LLM 调用前可改消息 | 直接返回修改后的 messages 或增量结果 |
| `model_select` | 模型切换通知 | 无 |
| `agent_start` | agent loop 开始 | 无 |
| `agent_end` | agent loop 结束 | 无 |
| `turn_start` | turn 开始 | 无 |
| `turn_end` | turn 结束 | 无 |

#### 3.4.3 tool / bash 事件

| event | 作用 | handler 返回值 |
|---|---|---|
| `tool_call` | 工具调用前拦截 | `block: bool`, `reason?: str` |
| `tool_result` | 工具结果后处理 | `content?`, `details?`, `isError?` |
| `user_bash` | 用户手动 bash 执行 | `operations?`, `result?` |

#### 3.4.4 规则说明

- `before_provider_request` 的返回值是整包替换，不做局部 patch
- `tool_call` 默认不改写，只做阻断或通过
- `tool_result` 允许修改内容、details 和错误标记
- `before_agent_start` 允许注入一条 custom message，并且可替换本轮 system prompt
- `input` 必须支持三态：
  - `continue`
  - `handled`
  - `transform`
- `session_before_*` 统一使用 cancel 语义，避免引入多套拦截模型

### 3.5 `ExtensionAPI` 事件/注册完整约定

建议 Python 版把 `ExtensionAPI` 约定成两类方法：

1. 注册类
   - `on`
   - `register_tool`
   - `register_command`
   - `register_shortcut`
   - `register_flag`
   - `register_message_renderer`
   - `register_provider`
2. 行为类
   - `send_message`
   - `send_user_message`
   - `append_entry`
   - `set_session_name`
   - `set_label`
   - `set_model`
   - `set_thinking_level`
   - `compact`
   - `shutdown`

这样 Python 实现里可以把“注册”和“执行”拆成两个不同对象，测试更容易。
```

## 3.6 Extension 协作者拆分

建议 Python 版把 `ExtensionAPI` 再拆成更细的协作者对象，而不是单类承载所有行为。

### 3.6.1 类图

```text
ExtensionAPI
  ├─ EventRegistry
  │    ├─ register handlers
  │    ├─ store priorities
  │    └─ emit events
  ├─ ToolRegistrationManager
  │    ├─ register tools
  │    ├─ resolve conflicts
  │    └─ expose tool info
  ├─ CommandRegistrationManager
  │    ├─ register commands
  │    ├─ register shortcuts
  │    └─ build slash command list
  ├─ FlagRegistrationManager
  │    ├─ register flags
  │    ├─ store defaults
  │    └─ expose parsed values
  ├─ ProviderRegistrationManager
  │    ├─ register providers
  │    ├─ queue pending providers
  │    └─ refresh registry
  ├─ SessionActionBridge
  │    ├─ send_message
  │    ├─ append_entry
  │    ├─ set_session_name
  │    └─ set_label
  ├─ ModelActionBridge
  │    ├─ set_model
  │    ├─ set_thinking_level
  │    └─ get_context_usage
  ├─ ToolActionBridge
  │    ├─ get_active_tools
  │    ├─ set_active_tools
  │    └─ refresh_tools
  ├─ ControlBridge
  │    ├─ abort
  │    ├─ shutdown
  │    └─ compact
  └─ UIBridge
       ├─ select / confirm / input
       ├─ setStatus / setWidget / setTitle
       └─ editor / pasteToEditor / setEditorComponent
```

### 3.6.2 依赖方向

```text
ExtensionAPI -> EventRegistry
ExtensionAPI -> ToolRegistrationManager
ExtensionAPI -> CommandRegistrationManager
ExtensionAPI -> FlagRegistrationManager
ExtensionAPI -> ProviderRegistrationManager
ExtensionAPI -> SessionActionBridge
ExtensionAPI -> ModelActionBridge
ExtensionAPI -> ToolActionBridge
ExtensionAPI -> ControlBridge
ExtensionAPI -> UIBridge
```

### 3.6.3 职责边界

- `EventRegistry` 只管理订阅和发射
- `ToolRegistrationManager` 只管工具定义和冲突检测
- `CommandRegistrationManager` 只管 slash command 和 shortcut
- `FlagRegistrationManager` 只管 CLI flag 及默认值
- `ProviderRegistrationManager` 只管 provider 注册与刷新
- `SessionActionBridge` 只做 session 写入，不决定业务策略
- `ModelActionBridge` 只做模型状态读写
- `ToolActionBridge` 只做工具可见性和激活态
- `ControlBridge` 只做 abort / shutdown / compact
- `UIBridge` 只做交互层封装

## 3.7 事件处理伪代码

### 3.7.1 `emit(event)`

```text
look up all handlers registered for event.type
sort by priority / registration order
for each handler:
    call handler(event, context)
    if handler returns cancel/block:
        stop propagation and return the result
    if handler returns a mutation:
        merge mutation into the running event result
return final aggregated result
```

### 3.7.2 `input` 事件

```text
user text enters system
  -> fire input event
  -> if handler returns handled:
         stop normal prompt path
  -> if handler returns transform:
         replace text/images and continue
  -> if handler returns continue or nothing:
         continue normal prompt path
```

### 3.7.3 `before_provider_request`

```text
context prepared
  -> fire before_provider_request
  -> if handler returns replacement payload:
         use replacement payload
  -> otherwise keep original payload
```

### 3.7.4 `tool_call`

```text
tool call about to execute
  -> fire tool_call
  -> if handler returns block:
         skip tool execution and surface reason
  -> otherwise execute tool normally
```

### 3.7.5 `tool_result`

```text
tool has finished
  -> fire tool_result
  -> if handler returns modified content/details/isError:
         merge into final tool result
  -> append final result into session
```

### 3.7.6 `before_agent_start`

```text
prompt collected and expanded
  -> fire before_agent_start
  -> if handler injects custom message:
         prepend or append it according to policy
  -> if handler replaces system prompt:
         use chained system prompt result
  -> continue into agent loop
```

### 3.7.7 session control hooks

```text
session_before_switch / session_before_fork / session_before_compact / session_before_tree
  -> fire hook
  -> if cancel:
         abort action
  -> otherwise continue
  -> after action, fire corresponding session_* event
```

### 3.7.8 `user_bash`

```text
user triggers ! or !!
  -> fire user_bash
  -> if handler returns full result:
         bypass default shell execution
  -> otherwise apply custom operations or default bash executor
```

### 3.7.9 结果合并原则

- `cancel` / `block` 优先于任何增量修改
- `transform` 优先于原始输入
- 同类 mutation 采用“后写覆盖前写”的方式
- 只允许明显安全的事件返回完整替换结果
- 事件处理必须是确定性的，不能依赖非显式顺序

## 4. SessionManager 文件操作伪代码

### 4.1 `_rewriteFile()`

```text
if persist is disabled or sessionFile is missing:
    return

serialize every entry in fileEntries as JSONL
write the whole file atomically
set flushed = true
```

建议 Python 版使用“先写临时文件，再替换目标文件”的方式，避免中断导致 session 文件损坏。

### 4.2 `_persist(entry)`

```text
if persist is disabled or sessionFile is missing:
    return

if there is no assistant message yet:
    do not write anything
    set flushed = false
    return

if flushed is false:
    write all current fileEntries in order
    set flushed = true
else:
    append only the new entry line
```

这个逻辑的核心目的是避免“session 只有 header + 用户首条消息，却在首个 assistant 回应前就写坏文件”的情况。

### 4.3 `set_session_file(path)`

```text
normalize path
if file exists:
    load entries from JSONL
    if file is empty or invalid:
        start a fresh session at that path
    if migration needed:
        migrate in memory
        rewrite whole file
    rebuild indexes
    set flushed = true
else:
    create a new session in memory
    do not create file until first assistant message
```

### 4.4 `fork_from(source, target_cwd, session_dir)`

```text
load source entries
validate header exists
create new session file
write new session header with parentSession = source path
copy all non-header entries verbatim
return SessionManager bound to the new file
```

### 4.5 `append_xxx()`

```text
build typed entry
assign id using current entry index / uuid generator
set parentId = leafId
push to in-memory list
update id index and leaf pointer
if persistence enabled:
    persist incrementally
```

### 4.6 `build_session_context()`

```text
walk from leaf to root using parentId
find latest compaction if any
emit compaction summary first
emit retained path from firstKeptEntryId onward
emit entries after compaction
convert custom_message into user-visible context messages
ignore custom, label, session_info
return messages + model + thinking level
```

## 5. 单元测试清单

### 5.1 基础解析

- 解析空文件返回空 entries
- 解析带 header 的标准 JSONL 文件成功
- 遇到空行应忽略
- 遇到坏行应报错或触发重建策略

### 5.2 migration

- v1 文件能补齐 `id` / `parentId`
- v1 `compaction.firstKeptEntryIndex` 能正确迁移成 `firstKeptEntryId`
- v2 `hookMessage` 能迁移成 `custom`
- migration 后 header.version 应为 `3`

### 5.3 append / persist

- 首个用户消息不应立刻把不完整文件写死
- 首个 assistant 消息到来后应一次性写出完整文件
- 后续追加应增量写入
- `appendCompaction()` / `appendBranchSummary()` 应产生专用 entry

### 5.4 branch / fork / tree

- `branch()` 只移动 leaf，不修改历史
- `branchWithSummary()` 会新增 branch_summary entry
- `fork_from()` 会产生新的 session 文件且保留历史
- `get_tree()` 应正确恢复树结构和 label

### 5.5 context 构建

- `build_session_context()` 应正确跳过 `custom`
- `custom_message` 应进入上下文
- `compaction` 应在上下文中先于 kept messages 出现
- `label` 和 `session_info` 不应进入上下文

### 5.6 可靠性

- `_rewriteFile()` 应避免半写状态
- `set_session_file()` 遇到空文件应重建新 session
- `fork_from()` 遇到无 header 文件应失败
- `reload()` 后索引和 leaf 应恢复正确

### 5.7 回归测试建议

- 复制 `session-manager/*.test.ts` 的语义场景到 Python
- 重点保留：
  - tree traversal
  - save entry
  - migration
  - labels
  - file operations
  - build context

## 3. 迁移步骤

### Phase 0: 契约冻结

- 冻结 message / session / tool result schema
- 冻结 event names
- 冻结 storage key names
- 冻结 event file schema

### Phase 1: 协议层

- 实现 `Model`
- 实现 `Context`
- 实现 `Message` / `AssistantMessage`
- 实现 provider registry
- 实现 stream event protocol

### Phase 2: Agent runtime

- 实现 `Agent`
- 实现 tool execution
- 实现 before/after hooks
- 实现 retry / compaction

### Phase 3: Session runtime

- 实现 append-only session tree
- 实现 branch / fork / tree
- 实现 session persistence
- 实现 settings layering

### Phase 4: Product layers

- CLI coding agent
- Slack mom
- GPU pods CLI
- Web UI

## 4. 迁移优先级

### 第一优先

- `pi-ai` 协议和 provider 兼容
- `pi-agent-core` 状态机
- session persistence
- Slack / CLI 主路径

### 第二优先

- extensions
- compaction
- branch/tree
- attachments and artifacts

### 第三优先

- 更完整的 TUI / web UI polish
- 包管理
- 高级资源发现
- 更复杂的远端 pod 维护功能

## 5. 兼容性检查点

Python 版上线前要逐项验证：

- partial tool JSON 流式解析
- thinking / reasoning 的跨 provider 重放
- aborted / error 的最终消息语义
- tool result 图片支持
- session fork / branch / tree 行为
- extension 冲突检测
- storage metadata 与 full data 的一致性

## 6. 建议的目录结构

```text
ppi/
  ai/
  agent/
  cli/
  session/
  resources/
  settings/
  web/
  slack/
  pods/
  storage/
  scheduler/
  sandbox/
```

## 7. 验收标准

- 能重放一条完整的 agent 会话。
- 能在 fork / branch / tree 后继续对话。
- 能在 Slack 和 web 两端使用同一套 session/agent 核心。
- 能把 `mom` 的事件调度和 `pods` 的远端启动分别替换到 Python 后端。
- 能保留现有最重要的用户行为，而不要求 UI 100% 复刻。
