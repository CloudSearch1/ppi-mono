# `pi_cli` 三种 mode 的执行时序图

这份文档把 `interactive`、`print`、`rpc` 三种模式拆开，重点描述：

- 谁负责初始化
- 谁负责事件订阅
- 谁负责输入输出
- 谁负责退出

---

## 1. 总入口时序

```text
main(argv)
  ├── handlePackageCommand?
  ├── handleConfigCommand?
  ├── runMigrations()
  ├── parseArgs() x2
  ├── load settings / auth / models / resources
  ├── createSessionManager()
  ├── buildSessionOptions()
  ├── createAgentSession()
  └── dispatch mode
       ├── interactive -> InteractiveMode.run()
       ├── print       -> runPrintMode()
       └── rpc         -> runRpcMode()
```

主入口有两个阶段的参数解析：

1. 第一次解析用于发现 extension flags 和资源路径
2. 第二次解析用于把 extension flags 也纳入正式参数

这是为了让扩展可以在 CLI 解析阶段就注册自己的 flag。

---

## 2. `interactive` mode 时序图

### 2.1 启动阶段

```text
main()
  -> createAgentSession()
  -> new InteractiveMode(session, options)
  -> InteractiveMode.init()
```

```text
InteractiveMode.init()
  ├── ensure fd / rg tools
  ├── build TUI containers
  ├── build header / footer / editor
  ├── init theme
  ├── setup autocomplete
  ├── setup key handlers
  ├── setup editor submit handler
  ├── ui.start()
  ├── initExtensions()
  ├── renderInitialMessages()
  ├── subscribeToAgent()
  ├── register theme watcher
  └── update footer/provider counts
```

### 2.2 运行阶段

```text
InteractiveMode.run()
  ├── check version / package updates / tmux setup
  ├── show startup warnings
  ├── send initialMessage / initialMessages
  └── while true
       ├── getUserInput()
       └── session.prompt(userInput)
```

### 2.3 输入链路

```text
user types in editor
  -> editor submit handler
  -> InteractiveMode.getUserInput()
  -> session.prompt()
  -> AgentSession.prompt()
  -> Agent.stream / tool loop
  -> AgentSession event handler
  -> InteractiveMode.subscribeToAgent()
  -> UI invalidate / requestRender
```

### 2.4 事件订阅链路

```text
session.subscribe(event)
  -> update chat containers
  -> update loader / pending tool cards
  -> update footer stats
  -> show warnings/errors
  -> ui.requestRender()
```

### 2.5 交互中的特殊分支

```text
if /command
  -> execute command immediately
  -> may open overlay / selector / loader
  -> may mutate session state

if streaming
  -> queued steer / follow-up

if compaction / retry
  -> show loader
  -> suspend some editor actions
```

### 2.6 退出

```text
stop()
  ├── stop UI
  ├── detach listeners
  ├── stop theme watcher
  └── flush pending output
```

### 2.7 交互 mode 的核心语义

`interactive` mode 不是“一个 readline loop”，而是：

- TUI 作为主事件循环
- editor 只是输入源之一
- session 事件驱动 UI 更新
- overlays / dialogs / widgets 都会暂时替换 editor

---

## 3. `print` mode 时序图

### 3.1 总体流程

```text
main()
  -> createAgentSession()
  -> runPrintMode(session, options)
  -> flush stdout
  -> exit
```

### 3.2 运行链路

```text
runPrintMode()
  ├── if json mode: print session header
  ├── bindExtensions(no UI)
  ├── subscribe session events
  ├── prompt initialMessage if any
  ├── prompt extra messages sequentially
  ├── if text mode: print final assistant message
  └── flush stdout
```

### 3.3 事件输出

```text
session.subscribe(event)
  -> if mode == json
       print JSON event line
```

### 3.4 text vs json

```text
text mode
  -> 只输出最终 assistant 文本

json mode
  -> 输出 header + 每个 AgentSessionEvent
  -> 适合外部程序消费
```

### 3.5 终止条件

```text
final assistant message printed
  -> stdout flush
  -> process exits
```

### 3.6 print mode 的核心语义

print mode 是最小闭环：

- 没有 TUI
- 没有交互 overlay
- 只有事件流和最终输出
- 仍然保留 session persistence 和 extension hooks

---

## 4. `rpc` mode 时序图

### 4.1 总体流程

```text
main()
  -> createAgentSession()
  -> runRpcMode(session)
  -> attach jsonl line reader to stdin
  -> loop forever
```

### 4.2 启动链路

```text
runRpcMode()
  ├── create RPC output helpers
  ├── build pending extension UI request map
  ├── create RPC ExtensionUIContext
  ├── bindExtensions(RPC UI)
  ├── subscribe session events -> stdout JSONL
  └── attachJsonlLineReader(stdin)
```

### 4.3 输入链路

```text
stdin JSON line
  -> JSON.parse
  -> if extension_ui_response:
       resolve pending UI promise
  -> else:
       handleCommand(command)
       -> output response line
```

### 4.4 命令流

```text
prompt
  -> session.prompt()
  -> immediate response ack
  -> async events continue streaming

steer / follow_up / abort
  -> call AgentSession methods directly

get_state / get_messages / get_commands
  -> query session state and reply synchronously
```

### 4.5 extension UI bridge

```text
extension asks for UI
  -> RPC ExtensionUIContext emits extension_ui_request
  -> host replies with extension_ui_response
  -> promise resolves
```

### 4.6 shutdown

```text
session.shutdown handler
  -> set shutdownRequested
  -> after current command finishes:
       emit session_shutdown
       pause stdin
       exit process
```

### 4.7 rpc mode 的核心语义

rpc mode 是一个“headless event bridge”：

- stdin 是命令通道
- stdout 是事件/响应通道
- extension UI 通过 request/response 对接宿主
- 适合嵌入到 Python、Rust、Go 或其他宿主进程中

---

## 5. 三种 mode 的差异

| Mode | 输入 | 输出 | UI | 退出方式 |
|---|---|---|---|---|
| interactive | TUI editor + overlays | TUI render | 完整终端 UI | 用户主动退出 |
| print | argv + stdin | text 或 JSONL | 无 | 打印后退出 |
| rpc | stdin JSONL commands | stdout JSONL events/responses | 宿主提供 UI | 宿主控制 shutdown |

---

## 6. 统一的共享事实

三种 mode 都共享同一条底层事实：

```text
CLI
  -> createAgentSession()
  -> AgentSession
  -> Agent
  -> SessionManager
```

因此 Python 重写时，mode 层最好不要复制核心编排逻辑，而是只做：

- 输入适配
- 输出适配
- UI / protocol bridge
- 退出控制

---

## 7. Python 落地建议

### interactive

推荐：

- `textual` 做界面壳
- `prompt_toolkit` 做输入编辑

### print

推荐：

- 直接用 `asyncio` + stdout
- JSONL 模式作为外部程序接口

### rpc

推荐：

- `stdin/stdout` JSONL 协议
- 可选 `FastAPI` / WebSocket 作为另一个宿主协议层

如果你要先做最小可用版本，建议优先级是：

1. `print`
2. `rpc`
3. `interactive`

因为前两者能最快验证 core/session/model 语义是否对齐。

---

## 8. 参数与退出码约定

`modes/shared.py` 里的解析层和退出码应当遵循下面这套约定，作为 Python 重写时的统一接口边界。

### 8.1 参数约定

- `--mode`
  - 只在总入口 `pimono` / `cli.main` 中解析
  - 取值限定为 `interactive`、`print`、`rpc`
- `--session-id`
  - 交互模式和 RPC 模式都可以接受
  - 语义是“预览或绑定到指定 session”
- `--theme`
  - 仅用于 interactive 预览
- `--json`
  - 仅用于 print 模式
  - 表示输出 JSONL / 结构化事件流
- `--input-fd` / `--output-fd`
  - 仅用于 RPC 模式
  - 作为宿主进程与 shell 之间的 fd 绑定参数

### 8.2 退出码约定

- `0` -> 正常完成
- `1` -> 运行时失败
- `2` -> 参数非法或模式不支持

### 8.3 统一分发规则

总入口应该只做两件事：

1. 解析统一参数
2. 根据 `mode` 分发到对应 mode 实例

不建议把以下逻辑塞进 `cli/main.py`：

- session persistence
- tool execution
- extension dispatch
- provider/model resolution

这些都应该落在 `AgentSession` 和 `core` 层。
