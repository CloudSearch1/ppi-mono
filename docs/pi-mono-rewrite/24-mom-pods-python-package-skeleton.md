# `mom` / `pods` Python 包目录骨架

这份文档把 `mom` 和 `pods` 收敛成一套可以直接开始落地的 Python 包结构。

目标不是一次性写全，而是先把“入口、状态、适配器、运行时、命令层”这些边界分清楚，后续实现时可以按文件逐步填充。

---

## 1. 总体分层

建议在 Python 重写里保留五个顶层域：

- `pimono.ai`：LLM 协议层
- `pimono.agent_core`：agent loop / tool loop
- `pimono.coding_agent`：session / settings / resources / extensions
- `pimono.mom`：Slack runtime / workspace / scheduler / sandbox
- `pimono.pods`：pod 配置 / SSH / model planner / CLI commands

其中 `mom` 和 `pods` 都应尽量依赖“共享协议层”，不要反向依赖彼此的具体实现。

---

## 2. 推荐目录树

下面是一版更偏实现友好的目录结构。

```text
pi-mono-py/
├── pyproject.toml
├── README.md
└── src/
    └── pimono/
        ├── __init__.py
        ├── shared/
        │   ├── __init__.py
        │   ├── types.py
        │   ├── paths.py
        │   └── protocols.py
        ├── ai/
        │   └── ...
        ├── agent_core/
        │   └── ...
        ├── coding_agent/
        │   └── ...
        ├── mom/
        │   ├── __init__.py
        │   ├── main.py
        │   ├── types.py
        │   ├── runtime.py
        │   ├── slack/
        │   │   ├── __init__.py
        │   │   ├── bot.py
        │   │   ├── context.py
        │   │   ├── handlers.py
        │   │   └── transport.py
        │   ├── workspace/
        │   │   ├── __init__.py
        │   │   ├── store.py
        │   │   ├── attachments.py
        │   │   ├── sync.py
        │   │   └── memory.py
        │   ├── scheduler/
        │   │   ├── __init__.py
        │   │   ├── watcher.py
        │   │   ├── parser.py
        │   │   └── planner.py
        │   ├── sandbox/
        │   │   ├── __init__.py
        │   │   ├── executor.py
        │   │   └── config.py
        │   └── agent/
        │       ├── __init__.py
        │       ├── runner.py
        │       └── bridge.py
        └── pods/
            ├── __init__.py
            ├── cli.py
            ├── types.py
            ├── config.py
            ├── ssh.py
            ├── models.py
            ├── runtime.py
            ├── prompt.py
            └── commands/
                ├── __init__.py
                ├── setup.py
                ├── start.py
                ├── stop.py
                ├── logs.py
                └── agent.py
```

---

## 3. `mom` 目录职责

### 3.1 `pimono.mom.main`

这里放 CLI 或服务入口：

- 读取 env
- 初始化 Slack runtime
- 初始化 workspace / store
- 启动 scheduler
- 绑定 signal handler

### 3.2 `pimono.mom.slack`

这里处理 Slack 适配：

- `bot.py`：socket mode / event routing / queue
- `context.py`：回复、线程回复、typing、working、delete
- `handlers.py`：mention / dm / file_share / stop 分流
- `transport.py`：Web API 封装

### 3.3 `pimono.mom.workspace`

这里放工作区语义：

- `store.py`：`log.jsonl` / channel dir / dedupe / bot response log
- `attachments.py`：附件索引和下载
- `sync.py`：`log.jsonl` -> `SessionManager`
- `memory.py`：memory 文件加载和合并

### 3.4 `pimono.mom.scheduler`

这里放文件型调度任务：

- `watcher.py`：监视 `events/`
- `parser.py`：解析 immediate / one-shot / periodic
- `planner.py`：调度到 `asyncio` / cron backend

### 3.5 `pimono.mom.sandbox`

这里放执行隔离：

- `config.py`：host / docker sandbox config
- `executor.py`：host executor / docker executor

### 3.6 `pimono.mom.agent`

这里放 agent 运行桥接：

- `runner.py`：把上下文、store、tools 交给 agent loop
- `bridge.py`：把 SlackContext 和 AgentContext 互相转换

---

## 4. `pods` 目录职责

### 4.1 `pimono.pods.cli`

这里是命令总入口：

- `pi pods setup`
- `pi pods active`
- `pi pods remove`
- `pi start`
- `pi stop`
- `pi list`
- `pi logs`
- `pi agent`

### 4.2 `pimono.pods.config`

本地 source of truth：

- 读写 `pods.json`
- active pod 管理
- model runtime metadata 保存

### 4.3 `pimono.pods.ssh`

远端操作适配层：

- `sshExec`
- `sshExecStream`
- `scpFile`
- 交互 shell

### 4.4 `pimono.pods.models`

模型和硬件规划：

- 模型兼容性矩阵
- GPU 选择
- port 分配
- model config 选择

### 4.5 `pimono.pods.runtime`

远端 vLLM 生命周期：

- 启动脚本渲染
- 监控 startup success
- 监控日志
- 停止 process tree

### 4.6 `pimono.pods.commands`

命令级编排拆分为独立文件，便于测试：

- `setup.py`：pod bootstrap
- `start.py`：模型启动
- `stop.py`：模型停止
- `logs.py`：日志查看
- `agent.py`：交互式代理入口

---

## 5. 依赖方向

建议保持以下依赖方向：

```text
pimono.shared
  -> pimono.ai
  -> pimono.agent_core
  -> pimono.coding_agent
  -> pimono.mom
  -> pimono.pods
```

具体约束：

- `mom` 可以依赖 `coding_agent` 的 session/settings 协议
- `pods` 可以依赖 `ai` 的模型与消息协议，但不应依赖 `mom`
- `mom` 和 `pods` 的 CLI 层应只依赖各自的 runtime/service 层

---

## 6. 最小可运行骨架

如果先做 MVP，建议只落这些文件：

- `pimono/mom/main.py`
- `pimono/mom/slack/bot.py`
- `pimono/mom/workspace/store.py`
- `pimono/mom/workspace/sync.py`
- `pimono/mom/scheduler/watcher.py`
- `pimono/pods/cli.py`
- `pimono/pods/config.py`
- `pimono/pods/ssh.py`
- `pimono/pods/models.py`
- `pimono/pods/runtime.py`
- `pimono/pods/commands/setup.py`
- `pimono/pods/commands/start.py`
- `pimono/pods/commands/stop.py`
- `pimono/pods/commands/logs.py`
- `pimono/pods/commands/agent.py`

这样就能先跑通“配置 -> 远端 -> 模型 -> 日志 -> agent”的主链路。

---

## 7. 命名建议

为了和现有 `pi-mono` 的语义一致，建议：

- `mom` 侧保留 `workspace`、`scheduler`、`sandbox`、`slack`
- `pods` 侧保留 `config`、`ssh`、`models`、`runtime`
- shared 协议放到 `pimono.shared`

这样可以避免把所有逻辑都塞进一个 `utils.py` 或 `core.py`。

