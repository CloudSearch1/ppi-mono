# `packages/coding-agent/src/core` 调用流程图

这份文档把 `AgentSession`、`SessionManager`、`ModelRegistry`、`SettingsManager` 串成一条可实现的调用链，重点看“谁负责决策，谁负责持久化，谁负责恢复”。

---

## 1. 总体关系

```text
CLI / mode
   │
   ▼
createAgentSession()
   │
   ├── SettingsManager
   ├── AuthStorage
   ├── ModelRegistry
   ├── SessionManager
   ├── ResourceLoader
   └── Agent
           │
           ▼
       AgentSession
           │
           ├── session persistence
           ├── extension runner
           ├── compaction
           ├── auto-retry
           ├── bash execution
           └── session switch / fork / tree
```

核心设计是：

- `createAgentSession()` 负责组装依赖
- `AgentSession` 负责业务编排
- `SessionManager` 负责事实存储
- `ModelRegistry` 负责模型与鉴权
- `SettingsManager` 负责配置层叠和写回

---

## 2. 启动流程

### 2.1 `main.ts`

入口链路大致是：

```text
main(argv)
  ├── parseArgs()
  ├── handle package/config commands
  ├── runMigrations()
  ├── load settings
  ├── createAgentSession()
  └── choose mode
       ├── interactive
       ├── print
       └── rpc
```

### 2.2 `createAgentSession()`

`sdk.ts` 里的构建顺序非常关键：

```text
CreateAgentSessionOptions
  ├── AuthStorage
  ├── ModelRegistry
  ├── SettingsManager
  ├── SessionManager
  ├── ResourceLoader
  └── Agent
```

推荐把它理解为“依赖注入工厂”。

### 2.3 具体流程

```text
createAgentSession()
  ├── resolve cwd / agentDir
  ├── create AuthStorage
  ├── create ModelRegistry
  ├── create SettingsManager
  ├── create SessionManager
  ├── create / reload ResourceLoader
  ├── restore session context
  ├── resolve model
  ├── resolve thinking level
  ├── construct Agent
  ├── restore agent messages
  ├── append initial model/thinking entries
  └── construct AgentSession
```

---

## 3. `ModelRegistry` 调用流程

### 3.1 初始化

```text
new ModelRegistry(authStorage, modelsJsonPath)
  ├── set fallback resolver on AuthStorage
  └── loadModels()
       ├── loadCustomModels()
       ├── loadBuiltInModels()
       ├── merge custom models
       └── apply OAuth model modifiers
```

### 3.2 运行时刷新

```text
ModelRegistry.refresh()
  ├── clear custom API key cache
  ├── resetApiProviders()
  ├── resetOAuthProviders()
  ├── loadModels()
  └── re-apply registered provider configs
```

### 3.3 查询流程

```text
getAll() / getAvailable()
  └── return cached model list

find(provider, modelId)
  └── search cached list

getApiKey(model) / getApiKeyForProvider(provider)
  └── resolve from AuthStorage
  └── fallback to custom provider apiKey config
```

### 3.4 关键语义

`ModelRegistry` 不是静态模型表，它还负责：

- custom provider registration
- runtime provider override
- oauth provider rebuild
- env / config / auth fallback

---

## 4. `SettingsManager` 调用流程

### 4.1 加载

```text
SettingsManager.create(cwd, agentDir)
  └── FileSettingsStorage
      ├── load global settings
      ├── load project settings
      ├── migrate old format
      └── deep merge
```

### 4.2 读写模型

```text
getXxx()
  └── return current merged settings

setXxx(value)
  ├── update in-memory merged settings
  ├── mark modified fields
  ├── enqueue write
  └── persist only changed fields
```

### 4.3 持久化

```text
save global/project
  ├── acquire file lock
  ├── merge only modified fields
  ├── write JSON
  └── clear modified markers
```

### 4.4 关键点

`SettingsManager` 处理的是“层叠配置 + 增量写回”，不是简单的 JSON 读写：

- global / project 两层
- nested object 深合并
- migration
- file lock
- queued writes

---

## 5. `SessionManager` 调用流程

### 5.1 初始化

```text
SessionManager.create(cwd)
  ├── resolve session dir
  ├── load session file
  ├── migrate entries
  ├── build id index
  ├── build label index
  └── set leaf pointer
```

### 5.2 追加事件

```text
appendMessage()
appendThinkingLevelChange()
appendModelChange()
appendCompaction()
appendCustomEntry()
appendCustomMessageEntry()
appendSessionInfo()
appendLabelChange()
```

共性流程：

```text
appendXXX()
  ├── generate id
  ├── create entry
  ├── push to fileEntries
  ├── update byId
  ├── move leafId
  └── persist to JSONL
```

### 5.3 读取上下文

```text
buildSessionContext()
  ├── walk from leaf to root
  ├── collect path entries
  ├── resolve thinking/model
  ├── resolve compaction boundary
  └── emit LLM messages
```

### 5.4 分支 / fork / tree

```text
branch(entryId)
  └── move leaf pointer to old entry

resetLeaf()
  └── leaf = null

branchWithSummary(entryId, summary)
  ├── move leaf pointer
  ├── append branch_summary entry
  └── keep history append-only

getTree()
  ├── build node map
  ├── attach children by parentId
  ├── resolve labels
  └── sort children by timestamp

createBranchedSession(leafId)
  ├── extract path
  ├── drop labels
  ├── write new header
  └── copy path entries
```

### 5.5 会话上下文恢复

```text
load existing session
  ├── buildSessionContext()
  ├── restore model from last model_change / assistant message
  ├── restore thinking level
  └── return session + warnings
```

---

## 6. `AgentSession` 总流程

### 6.1 构造

```text
new AgentSession(config)
  ├── subscribe to Agent events
  ├── install tool hooks
  ├── build runtime tool registry
  ├── bind extension runner
  └── initialize base system prompt
```

### 6.2 `prompt()` 入口

```text
prompt(text, options)
  ├── execute extension command if /command
  ├── emit input hook
  ├── expand skill/prompt templates
  ├── if streaming -> queue steer/followUp
  ├── validate model + api key
  ├── flush pending bash messages
  ├── run pre-compaction check
  ├── build user message + attachments
  ├── inject pending next-turn messages
  ├── emit before_agent_start hook
  ├── agent.prompt(messages)
  └── waitForRetry()
```

### 6.3 agent 事件处理

```text
_handleAgentEvent(event)
  ├── create retry promise for agent_end
  └── queue _processAgentEvent(event)

_processAgentEvent(event)
  ├── update steering/follow-up queues
  ├── emit extension event
  ├── notify listeners
  ├── persist message entries
  ├── track last assistant message
  ├── trigger auto-retry if needed
  └── trigger compaction if needed
```

### 6.4 事件到持久化

```text
message_end
  ├── user/assistant/toolResult -> SessionManager.appendMessage()
  └── custom -> SessionManager.appendCustomMessageEntry()

agent_end
  ├── maybe retry
  └── maybe compact
```

### 6.5 模型切换

```text
cycle model
  ├── query ModelRegistry.getAvailable()
  ├── validate api key
  ├── agent.setModel()
  ├── sessionManager.appendModelChange()
  ├── settingsManager.setDefaultModelAndProvider()
  └── adjust thinking level
```

### 6.6 thinking level

```text
setThinkingLevel(level)
  ├── clamp by model capability
  ├── agent.setThinkingLevel()
  ├── appendThinkingLevelChange()
  └── persist default in SettingsManager
```

### 6.7 compaction

```text
compact()
  ├── abort current work
  ├── build compaction preparation from SessionManager.getBranch()
  ├── emit session_before_compact hook
  ├── compact() or use extension result
  ├── SessionManager.appendCompaction()
  ├── agent.replaceMessages(buildSessionContext().messages)
  └── emit session_compact
```

### 6.8 auto-retry

```text
agent_end with retryable assistant error
  ├── create retry promise
  ├── remove error message from agent state
  ├── exponential backoff sleep
  ├── agent.continue()
  └── emit auto_retry_start / auto_retry_end
```

### 6.9 bash execution

```text
executeBash(command)
  ├── apply shell prefix
  ├── run shell executor
  ├── recordBashResult()
  └── append message to agent/session
```

### 6.10 session switch

```text
switchSession(path)
  ├── emit session_before_switch
  ├── abort current work
  ├── SessionManager.setSessionFile(path)
  ├── agent.sessionId = new session id
  ├── SessionManager.buildSessionContext()
  ├── agent.replaceMessages()
  ├── restore model if possible
  └── restore thinking level
```

---

## 7. 关键数据流图

### 7.1 新输入

```text
user input
  -> AgentSession.prompt()
  -> Agent.prompt()
  -> AgentSession._handleAgentEvent()
  -> SessionManager.appendMessage()
  -> UI listeners
```

### 7.2 工具调用

```text
assistant tool call
  -> Agent beforeToolCall
  -> ExtensionRunner.tool_call
  -> tool execute
  -> ExtensionRunner.tool_result
  -> Agent afterToolCall
  -> SessionManager.appendMessage(toolResult)
```

### 7.3 压缩

```text
context grows
  -> AgentSession._checkCompaction()
  -> prepareCompaction()
  -> compact()
  -> SessionManager.appendCompaction()
  -> Agent.replaceMessages()
```

### 7.4 恢复

```text
resume / switch / fork
  -> SessionManager.buildSessionContext()
  -> ModelRegistry.resolve model
  -> SettingsManager.resolve defaults
  -> Agent.replaceMessages()
  -> AgentSession rebind runtime
```

---

## 8. Python 重写时的拆分建议

如果按 Python 实现，建议把这四个对象拆开：

```text
SessionFactory
  -> 负责 createAgentSession()

AgentCoordinator
  -> 负责 AgentSession 的事件编排

SessionRepository
  -> 负责 SessionManager 的持久化和 tree

RuntimeCatalog
  -> 负责 ModelRegistry + SettingsManager
```

这样会比把所有逻辑塞进一个 `AgentSession` 类更容易测试，也更容易换 UI 层。
