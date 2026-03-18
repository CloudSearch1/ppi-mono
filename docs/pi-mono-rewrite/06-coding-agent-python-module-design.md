# `pi-coding-agent` Python 版模块级设计稿

这份文档基于 `packages/coding-agent` 的 README、`docs/*` 和 `src/*` 实现，整理成 Python 重写时可直接落地的模块设计。

## 1. 设计目标

- 保留当前项目的核心产品能力
- 用更清晰的 Python 模块边界重建 runtime
- 优先保证 session、tool、provider、extension、RPC 的行为一致
- 在不损失主要能力的前提下，减少前端和包管理复杂度

## 2. 推荐 Python 包划分

### `pi_ai`

职责：

- provider / model registry
- API key / OAuth 解析
- stream 协议适配
- 消息转换、token / usage 统计
- 跨 provider 兼容

不负责：

- session
- 工具执行
- UI
- 扩展加载

### `pi_agent_core`

职责：

- Agent 状态机
- tool 调度
- steering / follow-up 队列
- retry
- streaming orchestration
- 事件出口

### `pi_coding_agent`

职责：

- session tree
- settings
- skills / prompt templates / themes
- extension runtime
- bash / read / edit / write 工具集合
- interactive / print / rpc 运行模式

### `pi_ui`

职责：

- TUI
- RPC host UI bridge
- editor / selector / overlay / status bar

## 3. 模块内部分层

### 3.1 Bootstrap 层

入口文件建议只有一个：

- 解析 CLI
- 处理 migrations
- 初始化 settings / auth / model registry
- 加载 resources / extensions
- 创建 session
- 进入 runtime mode

建议拆出：

- `cli/args.py`
- `cli/main.py`

### 3.2 Config 层

建议保留两层配置：

- global
- project

核心能力：

- deep merge
- legacy migration
- file lock
- runtime override

### 3.3 Resource 层

建议把资源发现拆成两个阶段：

1. Discovery
   - 扫描目录
   - 解析来源和 scope
   - 处理冲突
2. Loading
   - 读取文件
   - 校验 frontmatter
   - 构建 prompt / skill / theme 对象

资源类型：

- skills
- prompt templates
- themes
- AGENTS / system prompt fragments
- extensions 资源路径

### 3.4 Session 层

建议使用 append-only JSONL 树。

核心对象：

- `SessionHeader`
- `SessionEntry`
- `SessionTreeNode`
- `SessionContext`
- `SessionManager`

语义：

- `id` / `parentId` 表示树
- `leaf_id` 表示当前活跃分支
- compaction / branch summary 作为显式节点存在

### 3.5 Runtime 层

`AgentSession` 是 Python 版最关键的聚合器。

它应该负责：

- 绑定 Agent
- 绑定 SessionManager
- 绑定 SettingsManager
- 绑定 ModelRegistry
- 绑定 ResourceLoader
- 绑定 ExtensionRuntime
- 处理 prompt / command / tool / compaction / fork / tree / reload

### 3.6 Extension 层

建议把 extension 当成“事件驱动的插件系统”，而不是脚本注入。

最重要的能力：

- 事件监听
- tool / command / flag / shortcut 注册
- provider registration
- UI context
- session / tree / compact / model hooks

## 4. 运行模式

### 4.1 Interactive

- 完整终端 UI
- 支持菜单、对话、编辑器、overlay、快捷键
- 适合日常使用

### 4.2 Print

- 适合脚本自动化
- 不依赖复杂 UI
- 输出最终回答或 JSON event stream

### 4.3 RPC

- 由外部宿主提供 UI
- Python 进程只提供协议和 agent runtime
- 适合嵌入桌面端、Web 容器、测试 harness

### 4.4 SDK

- 直接在 Python 代码里调用 `create_agent_session`
- 适合二次开发、测试和集成

## 5. 关键架构取舍

### 必须保留

- session 树
- session append-only
- compaction / branch summary
- tool 元信息
- provider compat
- extension hooks
- RPC 协议

### 可以简化

- npm/git package manager
- 复杂 TUI 小组件体系
- 主题热更新
- 过多 CLI 兼容命令
- 无关的辅助工具和 demo 逻辑

## 6. 推荐目录结构

```text
pi_coding_agent/
  cli/
  core/
    session/
    settings/
    resources/
    extensions/
    tools/
    compaction/
    rpc/
    modes/
  ui/
  docs/
```

## 7. 最小可用版本

如果先做 MVP，建议顺序如下：

1. session manager
2. settings manager
3. model registry
4. agent session
5. built-in tools
6. print mode
7. rpc mode
8. interactive mode
9. extensions
10. skills / prompt templates / compaction / tree

