# `mom`、`pods` 与 `web-ui` 设计分析

这份文档补齐 `pi-mono` 中三个“更上层”的包：

- `mom`: Slack 入口与工作区自动化
- `pods`: GPU pod / vLLM / agent CLI 管理
- `web-ui`: 浏览器侧 chat runtime、storage 和 artifacts/sandbox

它们都建立在 `pi-ai` 与 `pi-agent-core` 之上，但职责非常不同：

- `mom` 是“事件驱动的 Slack 代理”
- `pods` 是“模型部署与可执行环境管理”
- `web-ui` 是“前端 UI + 本地状态 + sandbox 运行时”

## 1. 模块职责与边界

### `mom`

`mom` 不是普通 Slack bot，而是一个“自我维护的工作区代理”。

它负责：

- 订阅 Slack Socket Mode 事件
- 将消息、附件、线程回复写入 channel 工作区
- 把 `log.jsonl` 同步到 `SessionManager`
- 为每个 channel 维持独立状态和独立 runner
- 在 host / Docker sandbox 中执行命令
- 用 `pi-coding-agent` 的 session / settings / model registry 驱动 LLM 运行

它不负责：

- provider 兼容
- agent loop 底层工具执行
- 浏览器 UI

关键入口：

- [`packages/mom/src/main.ts`](../../packages/mom/src/main.ts)
- [`packages/mom/src/slack.ts`](../../packages/mom/src/slack.ts)
- [`packages/mom/src/store.ts`](../../packages/mom/src/store.ts)
- [`packages/mom/src/context.ts`](../../packages/mom/src/context.ts)
- [`packages/mom/src/sandbox.ts`](../../packages/mom/src/sandbox.ts)

### `pods`

`pods` 是一个“模型部署、启动、观察、以及 agent 测试”工具链。

它负责：

- 配置 GPU pod
- 管理 SSH 连接与远程执行
- 自动生成 vLLM 启动参数
- 维护多模型、多 GPU、上下文窗口和 memory 策略
- 暴露 OpenAI-compatible API endpoint
- 提供一个 standalone agent CLI，用来验证模型与工具调用能力

它不负责：

- Slack / Web UI
- session 持久化和人机交互界面
- 自定义工具市场或 extension 系统

关键入口：

- [`packages/pods/README.md`](../../packages/pods/README.md)
- [`packages/pods/package.json`](../../packages/pods/package.json)

### `web-ui`

`web-ui` 是浏览器侧的 agent UI runtime，不只是“一个 chat 组件”。

它负责：

- `ChatPanel` 的整体布局
- `AgentInterface` 的消息流、输入、模型选择、thinking 选择
- IndexedDB 存储
- 代理和 provider key 处理
- attachments 加载与预览
- artifacts 管理与 sandbox 执行
- tool renderer 注册与消息 renderer 注册
- dialogs / settings / session list / custom providers

它不负责：

- provider 原生实现
- agent loop
- 业务级 session 复用逻辑

关键入口：

- [`packages/web-ui/src/index.ts`](../../packages/web-ui/src/index.ts)
- [`packages/web-ui/src/ChatPanel.ts`](../../packages/web-ui/src/ChatPanel.ts)
- [`packages/web-ui/src/components/AgentInterface.ts`](../../packages/web-ui/src/components/AgentInterface.ts)
- [`packages/web-ui/src/tools/artifacts/artifacts.ts`](../../packages/web-ui/src/tools/artifacts/artifacts.ts)

## 2. `mom` 架构

### 运行时拓扑

`mom` 的核心运行单元是“按 channel 分片”的状态机：

- 每个 Slack channel 对应一个本地目录
- 每个 channel 有自己的 `ChannelStore`
- 每个 channel 有自己的 `AgentRunner`
- 每个 channel 有自己的运行/停止状态

`main.ts` 里把这些状态挂在 `channelStates` 上，通过 `getState(channelId)` 懒创建。

参考实现：

- [`packages/mom/src/main.ts`](../../packages/mom/src/main.ts)
- [`packages/mom/src/slack.ts`](../../packages/mom/src/slack.ts)
- [`packages/mom/src/store.ts`](../../packages/mom/src/store.ts)

### Slack 适配层

`SlackBot` 是薄包装，但它承担了最重要的 I/O 行为：

- 维护用户/频道缓存
- 接收 Slack 事件
- 统一消息发送、更新、线程回复、删除、上传文件
- 记录 `log.jsonl`
- 将事件按 channel 入队，保证顺序执行

`SlackContext` 则是交给 agent 的“能力接口”，包含：

- `respond`
- `replaceMessage`
- `respondInThread`
- `setTyping`
- `uploadFile`
- `setWorking`
- `deleteMessage`

这层的设计本质上是“把 Slack 操作转换成 agent 可调用的副作用端口”。

参考实现：

- [`packages/mom/src/slack.ts`](../../packages/mom/src/slack.ts)
- [`packages/mom/src/main.ts`](../../packages/mom/src/main.ts)

### 工作区与持久化

`ChannelStore` 是 mom 的持久化核心。

它负责：

- channel 目录创建
- 附件命名与下载
- `log.jsonl` 追加写入
- bot response 归档
- 去重写入

附件路径和日志是分离的：

- `log.jsonl` 是可 grep 的历史源
- `attachments/` 是附件实体
- `context` 是同步给 LLM 的结构化视图

参考实现：

- [`packages/mom/src/store.ts`](../../packages/mom/src/store.ts)
- [`packages/mom/src/context.ts`](../../packages/mom/src/context.ts)

### Context 同步

`syncLogToSessionManager()` 是 mom 和 coding-agent 之间最关键的桥。

它做了三件事：

- 从 `log.jsonl` 找出尚未进入 session 的用户消息
- 规范化消息文本，去掉时间戳和 Slack 附件标记
- 以 `UserMessage` 形式追加到 `SessionManager`

这意味着：

- `log.jsonl` 是事实历史
- `SessionManager` 是 LLM 视角历史
- 两者不是同一个东西

参考实现：

- [`packages/mom/src/context.ts`](../../packages/mom/src/context.ts)

### Sandbox

`SandboxConfig` 只有两种模式：

- `host`
- `docker:<container>`

`createExecutor()` 返回统一 `Executor`，上层不应该关心底层是本机 shell 还是 `docker exec`。

这层的本质是“执行环境抽象”，而不是“安全沙箱”本身。

参考实现：

- [`packages/mom/src/sandbox.ts`](../../packages/mom/src/sandbox.ts)

### 行为特征

`mom` 的几个关键行为对重写非常重要：

- channel 级串行队列，避免同一频道并发回复互相打架
- main message + thread message 的双层输出
- long message 截断，但仍保留可追问的主线程
- `stop` 语义是中断当前 channel 的 agent 工作
- 事件消息和普通用户消息都复用同一个工作流
- `[SILENT]` 是一个重要的隐式协议，用于不刷屏的周期性检查

## 3. `pods` 架构

### 产品定位

`pods` 是一个模型基础设施工具，而不是一个聊天应用。

它的核心目标是：

- 让 GPU pod 上的 vLLM 部署变得可重复
- 让 agentic model 的 tool calling 参数可自动化配置
- 让多模型、多 GPU、不同 provider 的部署都走同一套命令

### 核心子域

从 README 和命令结构可以看出，`pods` 分成四个子域：

- Pod 管理
- Model 管理
- Agent / Chat interface
- 远程执行与观测

#### Pod 管理

负责：

- `setup`
- `active`
- `remove`
- `shell`
- `ssh`

这说明 `pods` 本质上维护的是一份“远程机器清单 + 当前激活项”。

#### Model 管理

负责：

- `start`
- `stop`
- `list`
- `logs`

同时它对模型有内建配置：

- 预定义模型
- GPU 数量建议
- context size / memory
- vLLM 特定参数

这意味着 `pods` 不是纯粹的 SSH wrapper，它还包含“模型启动规划器”。

#### Agent / Chat Interface

`pi agent` 和 `pi-agent` 两条路径说明这个包同时服务两种场景：

- 面向已部署模型的交互测试
- 面向任意 OpenAI-compatible endpoint 的 standalone agent

这个 standalone agent 对 Python 重写很有参考价值，因为它证明 `pi-agent-core` 本身就可以脱离 `pods` 使用。

#### 远程执行与观测

`pods` 的命令输出和日志观测是核心能力之一：

- 查看模型日志
- 查询运行状态
- 管理 session
- JSON output mode

### 设计上的关键点

`pods` 里最重要的不是 UI，而是“把 deployment 约束显式化”：

- 某个模型能不能跑在某个 GPU 组合上
- 需要什么 vLLM version
- 需要什么 tool parser
- context / memory 如何估计
- 是否需要 OpenAI Responses API

这类逻辑应该在 Python 中保持为独立的“planning layer”，不要混进 CLI parsing。

## 4. `web-ui` 架构

### 顶层组合

`ChatPanel` 是页面壳，`AgentInterface` 才是核心交互体。

`ChatPanel` 负责：

- 装配 `AgentInterface`
- 装配 `ArtifactsPanel`
- 根据屏幕大小切换布局
- 收集 attachments，注入 sandbox runtime providers
- 注册 artifacts tool renderer

`AgentInterface` 负责：

- 订阅 `Agent`
- 发送消息
- 展示 streaming message
- 处理模型选择、thinking level、附件、API key 提示
- 与 storage 交互

参考实现：

- [`packages/web-ui/src/ChatPanel.ts`](../../packages/web-ui/src/ChatPanel.ts)
- [`packages/web-ui/src/components/AgentInterface.ts`](../../packages/web-ui/src/components/AgentInterface.ts)

### Storage 层

`web-ui` 的 storage 是结构化的，不是简单的 `localStorage`：

- `SettingsStore`
- `ProviderKeysStore`
- `SessionsStore`
- `CustomProvidersStore`

`AppStorage` 作为总入口，统一挂载全局实例。

这层的抽象对 Python 版本很重要，因为它把“UI 状态”变成了可移植的持久层接口。

参考实现：

- [`packages/web-ui/src/storage/app-storage.ts`](../../packages/web-ui/src/storage/app-storage.ts)
- [`packages/web-ui/src/storage/stores/sessions-store.ts`](../../packages/web-ui/src/storage/stores/sessions-store.ts)
- [`packages/web-ui/src/storage/stores/provider-keys-store.ts`](../../packages/web-ui/src/storage/stores/provider-keys-store.ts)

### Message 模型

`web-ui` 在标准 agent 消息之外扩展了两个关键角色：

- `user-with-attachments`
- `artifact`

`defaultConvertToLlm()` 的职责是把这些 UI 特有消息折叠成 LLM 可理解的上下文，同时过滤掉不该喂给模型的内容。

这体现了一个非常重要的边界：

- UI 内部消息模型
- LLM 输入消息模型
- session 持久化消息模型

三者是相关但不相同的。

参考实现：

- [`packages/web-ui/src/components/Messages.ts`](../../packages/web-ui/src/components/Messages.ts)

### Attachments

`loadAttachment()` 支持多种输入：

- `File`
- `Blob`
- `ArrayBuffer`
- `URL`

并能处理：

- PDF
- DOCX
- PPTX
- XLSX
- 图片
- 文本

这意味着 Python 重写里需要一个独立的 attachment/document ingestion 模块，而不能把“读取附件”绑定在前端层。

参考实现：

- [`packages/web-ui/src/utils/attachment-utils.ts`](../../packages/web-ui/src/utils/attachment-utils.ts)

### Artifacts 与 sandbox

`ArtifactsPanel` 既是 UI 面板，也是一个真正的 `AgentTool`。

它还维护：

- artifact 状态
- HTML/SVG/Markdown/Text/Image 视图
- message replay
- sandbox runtime providers

`SandboxIframe` 和 runtime providers 的组合，说明 web-ui 并不只是“渲染 HTML”，而是在浏览器中跑了一个受控 JS 执行层。

参考实现：

- [`packages/web-ui/src/tools/artifacts/artifacts.ts`](../../packages/web-ui/src/tools/artifacts/artifacts.ts)
- [`packages/web-ui/src/components/SandboxedIframe.ts`](../../packages/web-ui/src/components/SandboxedIframe.ts)
- [`packages/web-ui/src/components/sandbox/RuntimeMessageRouter.ts`](../../packages/web-ui/src/components/sandbox/RuntimeMessageRouter.ts)

### Proxy 与自定义 provider

浏览器环境里，CORS 和 API key 存储是最现实的问题。

`web-ui` 提供了：

- `createStreamFn`
- `shouldUseProxyForProvider`
- `isCorsError`
- `applyProxyIfNeeded`
- custom provider 存储
- provider key prompt dialog

这使它能兼容：

- OpenAI-compatible APIs
- Ollama
- LM Studio
- vLLM
- 自定义代理

参考实现：

- [`packages/web-ui/src/index.ts`](../../packages/web-ui/src/index.ts)
- [`packages/web-ui/src/components/AgentInterface.ts`](../../packages/web-ui/src/components/AgentInterface.ts)

## 5. Python 重写建议

### `mom`

建议拆成：

- `pimono.mom.slack`
- `pimono.mom.workspace`
- `pimono.mom.sandbox`
- `pimono.mom.runner`
- `pimono.mom.events`

核心接口建议：

- `SlackTransport`
- `ChannelStore`
- `SlackContext`
- `MomRunner`
- `SandboxExecutor`

兼容点：

- channel 级队列
- `log.jsonl` / `context` 双轨
- 线程回复和主回复分离
- `[SILENT]` 协议
- stop / interrupt 语义

### `pods`

建议拆成：

- `pimono.pods.registry`
- `pimono.pods.remote`
- `pimono.pods.vllm`
- `pimono.pods.agent_cli`
- `pimono.pods.plan`

核心接口建议：

- `PodClient`
- `RemoteExecutor`
- `ModelPlan`
- `VllmLauncher`
- `AgentCli`

兼容点：

- 模型预设和 GPU 规划
- OpenAI-compatible endpoint 暴露
- standalone agent CLI
- 资源/上下文估计

### `web-ui`

如果将来 Python 也要提供前端侧接口，建议只保留“后端协议层”，而不是试图复刻全部 UI。

建议拆成：

- `pimono.web.storage`
- `pimono.web.attachments`
- `pimono.web.artifacts`
- `pimono.web.proxy`
- `pimono.web.messages`

核心接口建议：

- `AppStorage`
- `SessionStore`
- `ProviderKeyStore`
- `AttachmentLoader`
- `ArtifactStore`
- `ProxyResolver`
- `MessageTransformer`

兼容点：

- `artifact` 作为持久化消息类型
- attachment 转换成 content blocks
- session metadata 与 full session 分离
- provider key / proxy 的分层处理

## 6. 对 Python 重写的整体判断

`mom`、`pods`、`web-ui` 都不是“各自独立的小项目”，它们实际上是三种不同形态的 agent 入口：

- `mom` 是消息驱动入口
- `pods` 是运维驱动入口
- `web-ui` 是交互驱动入口

所以 Python 重写时，最合理的做法不是三套实现，而是共享同一组底层抽象：

- `pi_ai`
- `pi_agent_core`
- `pi_coding_agent`

然后在外层分别加：

- `pi_mom`
- `pi_pods`
- `pi_web_ui` 或纯前端适配层

