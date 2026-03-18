# `mom` 消息流 / 文件流 / scheduler 流时序图

这份文档把 `packages/mom` 拆成三条彼此耦合但职责清晰的运行链路：

- 消息流：Slack 事件如何进入 channel queue、写入 `log.jsonl`、同步到 `SessionManager`、再驱动 agent 输出
- 文件流：附件如何下载、落盘、映射到本地路径并进入后续上下文
- scheduler 流：`events/` 目录中的 JSON 事件如何被 watcher 扫描、校验、调度、执行

目标是为 Python 重写时保留语义边界，而不是照搬实现细节。

---

## 1. 模块职责

`mom` 的核心职责不是 Slack bot 外壳，而是一个带 Slack 入口的消息编排器：

- 接收 Slack mention / DM / file share
- 维护 per-channel 状态与队列
- 记录可追溯日志：`log.jsonl`
- 把历史事实同步到 session context：`context.jsonl` 对应的 `SessionManager`
- 在 sandbox 中执行 agent / tools
- 把结果回写到 Slack thread 或主消息
- 监听 `events/` 下的文件型调度任务

从设计上看，它更接近一个 “Slack-driven agent runtime”。

---

## 2. 消息流

### 2.1 入口

Slack 事件来自 `SlackBot`：

- `app_mention`
- `message`
- `stop` 关键字
- `backfill` / startup replay

关键对象是：

- `SlackBot`：负责 socket mode、web api、队列和事件路由
- `ChannelStore`：负责 `log.jsonl`、附件下载和重复消息去重
- `MomHandler`：负责实际的 agent 编排
- `SlackContext`：负责回复、线程回复、typing、working、文件上传

### 2.2 消息流时序

```text
Slack event
  -> SlackBot.setupEventHandlers()
  -> build SlackEvent
  -> ChannelStore.logMessage()
  -> ChannelStore.processAttachments()
  -> SlackBot.enqueueEvent() / direct handler call
  -> createMomContext()
  -> syncLogToSessionManager()
  -> AgentRunner.run()
  -> ctx.respond()/ctx.respondInThread()/ctx.uploadFile()
  -> SlackBot.postMessage()/updateMessage()/postInThread()
  -> ChannelStore.logBotResponse()
```

### 2.3 关键语义

- `log.jsonl` 是事实源，不是缓存
- 只有 `ChannelStore.logMessage()` 写日志
- attachment 先进入日志语义，再异步下载，不阻塞主流程
- bot response 也会写入 `log.jsonl`
- 队列按 channel 串行，避免同一频道并发冲突
- `stop` 是优先级最高的快捷命令，不走普通 queue

### 2.4 伪时序图

```text
User
  |
  | mention / DM / file_share
  v
SlackBot
  |--- logUserMessage() ----> log.jsonl
  |--- processAttachments --> attachments/*
  |--- enqueueEvent() -----> per-channel queue
  v
MomHandler
  |--- create context
  |--- sync log to session
  |--- run agent
  v
SlackContext
  |--- respond()
  |--- respondInThread()
  |--- setTyping()
  |--- uploadFile()
  v
Slack API
```

---

## 3. 文件流

### 3.1 入口与对象

附件流主要由 `ChannelStore` 承担：

- `processAttachments(channelId, files, timestamp)`
- `generateLocalFilename(originalName, timestamp)`
- `downloadAttachment(localPath, url)`
- `logMessage(...)`

### 3.2 文件流时序

```text
Slack event.files
  -> ChannelStore.processAttachments()
  -> generate local names
  -> enqueue pending downloads
  -> processDownloadQueue()
  -> fetch(url, Authorization: Bearer botToken)
  -> write file to workingDir/channelId/attachments/*
  -> log message references local attachment paths
```

### 3.3 设计要点

- 附件文件名带时间戳前缀，避免冲突
- local path 只记录相对工作目录路径，便于迁移和重放
- 下载是后台串行队列，不阻塞 Slack 主响应
- 失败只记 warning，不中断主消息处理
- `log.jsonl` 里保留附件元数据，后续 prompt / context sync 可以重建引用

### 3.4 Python 重写建议

建议把文件流拆成三个组件：

- `AttachmentIndexer`
- `AttachmentDownloader`
- `ChannelLogStore`

这样可以让消息同步和文件下载解耦，测试也更容易做。

---

## 4. Scheduler 流

### 4.1 入口与对象

调度任务来自 `events/` 目录中的 JSON 文件，由 `EventsWatcher` 处理：

- `start()` 先扫描已有文件
- `watch()` 监听增删改
- `parseEvent()` 校验 JSON
- `handleImmediate()` / `handleOneShot()` / `handlePeriodic()`
- `execute()` 转换为 synthetic SlackEvent

### 4.2 Scheduler 时序

```text
events/*.json
  -> EventsWatcher.start()
  -> scanExisting()
  -> handleFile()
  -> parseEvent()
  -> schedule by type
     - immediate -> execute now
     - one-shot   -> setTimeout
     - periodic   -> Cron
  -> execute()
  -> SlackBot.enqueueEvent()
  -> MomHandler.handleEvent()
```

### 4.3 事件类型

- `immediate`
  - 文件一旦被发现就执行
  - 旧文件会被视为 stale 并删除
- `one-shot`
  - 按 `at` 时间延迟执行
  - 过期则直接删除
- `periodic`
  - 按 cron 语法和 timezone 周期执行
  - 执行后不删除文件

### 4.4 失败与重试

- 读文件时会进行短暂重试，防止写入未完成
- JSON 缺字段会删除文件
- cron 语法非法会删除文件
- 队列满时会丢弃本次触发，但 immediate / one-shot 文件仍会清理

### 4.5 Python 重写建议

Python 侧可以用：

- `watchdog` 监听目录
- `apscheduler` 或 `croniter + asyncio` 做周期任务
- `asyncio.create_task()` 做 one-shot 延迟

如果需要保留“文件即调度”的语义，推荐把任务定义成可持久化事件对象，而不是把它们直接编成进程内定时器。

---

## 5. 关键接口清单

### 5.1 消息接口

```python
@dataclass(slots=True)
class SlackEvent:
    type: Literal["mention", "dm"]
    channel: str
    ts: str
    user: str
    text: str
    files: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
```

### 5.2 文件接口

```python
@dataclass(slots=True)
class Attachment:
    original: str
    local: str
```

### 5.3 调度接口

```python
@dataclass(slots=True)
class MomEvent:
    type: Literal["immediate", "one-shot", "periodic"]
    channel_id: str
    text: str
    at: str | None = None
    schedule: str | None = None
    timezone: str | None = None
```

---

## 6. Python 重写路径

### 推荐拆分

- `mom.core`：事件模型、上下文、handler 协议
- `mom.slack`：Slack adapter
- `mom.store`：log / attachment / download
- `mom.scheduler`：events 目录 watcher
- `mom.runtime`：agent 启动、session sync、sandbox

### 推荐技术栈

- Slack：`slack_bolt` 或 `slack_sdk`
- 异步：`asyncio`
- 文件监听：`watchdog`
- 调度：`APScheduler`
- 持久化：`jsonl` + `sqlite3`

### 取舍

- 如果优先保留行为一致性，先做 `log.jsonl` 和 `context sync`
- 如果优先做 MVP，可以先把 scheduler 延后，只实现消息流和文件流
- 如果要保留完整能力，不建议把调度逻辑完全塞进 Slack handler

