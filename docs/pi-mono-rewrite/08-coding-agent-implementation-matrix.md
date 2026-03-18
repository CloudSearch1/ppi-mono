# `pi-coding-agent` 实现对照表

这份表用于把当前 TypeScript 实现映射到 Python 实现，帮助拆分迁移任务。

## 1. 总体对照

| TS 模块 | 当前职责 | Python 对应模块 | 处理建议 |
|---|---|---|---|
| `src/main.ts` | 启动、参数解析、模式分发 | `cli/main.py` | 保留，逻辑可更薄 |
| `src/cli/args.ts` | CLI 参数定义与 help | `cli/args.py` | 保留 |
| `src/core/sdk.ts` | 构建 `AgentSession` | `runtime/session_factory.py` | 保留 |
| `src/core/agent-session.ts` | 核心编排 | `runtime/agent_session.py` | 必须保留 |
| `src/core/session-manager.ts` | session tree 持久化 | `session/session_manager.py` | 必须保留 |
| `src/core/settings-manager.ts` | settings 合并与迁移 | `settings/settings_manager.py` | 必须保留 |
| `src/core/model-registry.ts` | 模型与 provider 解析 | `models/model_registry.py` | 必须保留 |
| `src/core/resource-loader.ts` | 资源发现与加载 | `resources/resource_loader.py` | 保留，结构可简化 |
| `src/core/extensions/*` | 扩展系统 | `extensions/*` | 保留核心事件和注册能力 |
| `src/core/compaction/*` | compaction / branch summary | `compaction/*` | 必须保留 |
| `src/core/tools/*` | 内建工具 | `tools/*` | 保留最小集合 |
| `src/modes/interactive/*` | TUI | `ui/interactive/*` | 可重写，优先可用性 |
| `src/modes/rpc/*` | RPC 协议 | `rpc/*` | 保留 |
| `src/modes/print-mode.ts` | 非交互输出 | `modes/print.py` | 保留 |

## 2. 细节对照

### 2.1 Session

| 当前实现 | 作用 | Python 处理 |
|---|---|---|
| `SessionHeader` | 会话头 | 同名 dataclass |
| `MessageEntry` | 实际对话内容 | 同名 dataclass |
| `CompactionEntry` | 压缩摘要节点 | 保留 |
| `BranchSummaryEntry` | 分支摘要节点 | 保留 |
| `CustomEntry` | 扩展状态持久化 | 保留 |
| `CustomMessageEntry` | 扩展消息注入 | 保留 |
| `LabelEntry` | 书签 / 标记 | 保留 |
| `SessionInfoEntry` | 会话元数据 | 保留 |

### 2.2 Settings

| 当前实现 | 作用 | Python 处理 |
|---|---|---|
| global/project deep merge | 配置层叠 | 保留 |
| file lock 写入 | 防并发写损坏 | 保留 |
| 旧字段迁移 | 兼容旧配置 | 保留 |
| UI 细粒度参数 | TUI 调优 | 可后置 |

### 2.3 Extensions

| 当前实现 | 作用 | Python 处理 |
|---|---|---|
| `registerTool` | 动态工具 | 保留 |
| `registerCommand` | 命令扩展 | 保留 |
| `registerFlag` | CLI 扩展 | 保留 |
| `registerShortcut` | 键位扩展 | 保留但可先弱化 |
| `registerProvider` | provider 注入 | 保留 |
| `before_provider_request` | payload patch | 保留 |
| `tool_call` / `tool_result` | 工具拦截和改写 | 保留 |
| `session_before_*` | 会话控制 gate | 保留 |
| `ui.custom` / overlay | 复杂交互 | 可后置 |

### 2.4 Tools

| 当前工具 | 作用 | Python 处理 |
|---|---|---|
| `read` | 读取文件 | 必须保留 |
| `bash` | 执行 shell | 必须保留 |
| `edit` | 局部编辑 | 必须保留 |
| `write` | 写文件 | 必须保留 |
| `grep` | 搜索文本 | 可保留 |
| `find` | 查找文件 | 可保留 |
| `ls` | 列出目录 | 可保留 |

### 2.5 Compaction

| 当前实现 | 作用 | Python 处理 |
|---|---|---|
| `prepareCompaction()` | 找切点 | 必须保留 |
| `compact()` | 生成摘要 | 必须保留 |
| `prepareBranchEntries()` | 分支摘要准备 | 必须保留 |
| `generateBranchSummary()` | 分支摘要生成 | 必须保留 |
| `readFiles / modifiedFiles` | 文件操作追踪 | 必须保留 |

### 2.6 Modes

| 当前模式 | 作用 | Python 处理 |
|---|---|---|
| interactive | TUI | 保留 |
| print | 非交互 | 保留 |
| rpc | 宿主协议 | 保留 |
| sdk | 嵌入式调用 | 保留 |

## 3. 文件级补充说明

### `src/main.ts`

建议 Python 版拆成：

- 参数层
- 环境层
- session 层
- mode 层

不要让一个入口文件承载过多业务判断。

### `src/core/agent-session.ts`

这是最重的文件。Python 重写时建议分成：

- prompt flow
- model flow
- tool flow
- session flow
- extension flow
- compaction flow

### `src/core/extensions/runner.ts`

建议拆成：

- registry
- event dispatcher
- UI bridge
- conflict resolver

### `src/core/compaction/*`

建议保留文件操作追踪、切点选择和摘要格式，但把实现细节尽量封装。

### `src/modes/interactive/*`

这部分在 Python 里不建议照搬组件树，建议改为：

- view model
- render layer
- input router
- dialog manager

## 4. 迁移优先级

1. `SessionManager`
2. `SettingsManager`
3. `ModelRegistry`
4. `AgentSession`
5. `bash/read/edit/write`
6. `print mode`
7. `rpc mode`
8. `extensions`
9. `compaction`
10. `interactive UI`

## 5. 风险提示

- 如果 session 不做 append-only，后续 fork/tree/compaction 会很难复现
- 如果 RPC 和 interactive 分裂成两套 runtime，后期维护成本会很高
- 如果 extension 事件太少，很多现有能力会被迫写死
- 如果一开始就追求完整 TUI，交付会被 UI 复杂度拖慢

