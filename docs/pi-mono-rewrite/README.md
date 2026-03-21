# pi-mono 重写设计稿

这是对 `pi-mono` 的结构化分析，目标是为后续用 Python 重写提供可执行的设计基线。

## 文档索引

### 架构设计 (01-09)

| 编号 | 文档 | 描述 |
|------|------|------|
| 01 | [ai-agent-design.md](./01-ai-agent-design.md) | `pi-ai` 与 `pi-agent-core` 设计分析 |
| 02 | [coding-agent-architecture.md](./02-coding-agent-architecture.md) | 编码代理架构概述 |
| 03 | [python-rewrite-plan.md](./03-python-rewrite-plan.md) | Python 重写计划 |
| 04 | [coding-agent-core.md](./04-coding-agent-core.md) | 编码代理核心设计 |
| 05 | [ui-design.md](./05-ui-design.md) | UI 设计分析 |
| 06 | [agent-coding-agent-design.md](./06-agent-coding-agent-design.md) | `pi-agent-core` 与 `pi-coding-agent` 设计分析 |
| 07 | [coding-agent-python-api-draft.md](./07-coding-agent-python-api-draft.md) | `pi-coding-agent` Python 接口草案 |
| 08 | [coding-agent-implementation-matrix.md](./08-coding-agent-implementation-matrix.md) | 编码代理实现矩阵 |
| 09 | [python-package-structure.md](./09-python-package-structure.md) | Python 包结构 |

### 核心流程与协议 (10-16)

| 编号 | 文档 | 描述 |
|------|------|------|
| 10 | [coding-agent-core-call-flow.md](./10-coding-agent-core-call-flow.md) | 编码代理核心调用流程 |
| 11 | [pimono-ai-protocol-draft.md](./11-pimono-ai-protocol-draft.md) | pimono AI 协议草案 |
| 12 | [pi-cli-mode-sequence.md](./12-pi-cli-mode-sequence.md) | PI CLI 模式序列 |
| 13 | [python-protocols-and-dataclasses.md](./13-python-protocols-and-dataclasses.md) | Python 协议与数据类 |
| 16 | [python-implementation-task-breakdown.md](./16-python-implementation-task-breakdown.md) | Python 实现任务分解 |

### 模块设计 (17-25)

| 编号 | 文档 | 描述 |
|------|------|------|
| 17 | [mom-pods-protocols.md](./17-mom-pods-protocols.md) | mom/pods 协议 |
| 18 | [pimono-ai-code-skeleton.md](./18-pimono-ai-code-skeleton.md) | pimono AI 代码骨架 |
| 19 | [pimono-agent-core-interface.md](./19-pimono-agent-core-interface.md) | pimono agent core 接口 |
| 20 | [pimono-ai-code-templates.md](./20-pimono-ai-code-templates.md) | pimono AI 代码模板 |
| 21 | [pimono-coding-agent-interface-draft.md](./21-pimono-coding-agent-interface-draft.md) | pimono 编码代理接口草案 |
| 22 | [mom-message-file-scheduler-sequence.md](./22-mom-message-file-scheduler-sequence.md) | mom 消息文件调度序列 |
| 23 | [pods-command-sequences.md](./23-pods-command-sequences.md) | pods 命令序列 |
| 24 | [mom-pods-python-package-skeleton.md](./24-mom-pods-python-package-skeleton.md) | mom/pods Python 包骨架 |
| 25 | [mom-pods-python-protocols.md](./25-mom-pods-python-protocols.md) | mom/pods Python 协议 |

### 扩展与持久化 (26-29)

| 编号 | 文档 | 描述 |
|------|------|------|
| 26 | [ppi-ai-reuse-mapping.md](./26-ppi-ai-reuse-mapping.md) | ppi AI 复用映射 |
| 27 | [provider-templates-and-transports.md](./27-provider-templates-and-transports.md) | Provider 模板与传输 |
| 28 | [coding-agent-persistence-schemas.md](./28-coding-agent-persistence-schemas.md) | 编码代理持久化模式 |
| 29 | [coding-agent-jsonschema.md](./29-coding-agent-jsonschema.md) | `ppi_coding_agent` JSON Schema 文档 |

### 详细设计 (30-36)

| 编号 | 文档 | 描述 |
|------|------|------|
| 30 | [coding-agent-python-module-design.md](./30-coding-agent-python-module-design.md) | `pi-coding-agent` Python 版模块级设计稿 |
| 31 | [coding-agent-web-ui-total-design.md](./31-coding-agent-web-ui-total-design.md) | `pi-coding-agent` + `pi-web-ui` 总体设计 |
| 32 | [mom-pods-web-ui-design.md](./32-mom-pods-web-ui-design.md) | `mom`、`pods` 与 `web-ui` 设计分析 |
| 33 | [interface-spec-and-migration.md](./33-interface-spec-and-migration.md) | Python 重写接口规范与迁移步骤 |
| 34 | [python-package-layout.md](./34-python-package-layout.md) | Python 版目录结构与接口草案 |
| 35 | [python-package-structure-files.md](./35-python-package-structure-files.md) | Python 包结构文件 |
| 36 | [mom-pods-design.md](./36-mom-pods-design.md) | Python Rewrite Design: `mom` + `pods` |

## 示例

- [examples/provider-registry.json](./examples/provider-registry.json) - Provider 注册示例

## 说明

- 这里的内容基于仓库内 README 和源码阅读，不依赖外部推测。
- 重点关注三个层次：`pi-ai` 协议层、`pi-agent-core` 编排层、`pi-coding-agent` 产品层。
- 后续如果继续补充分析，优先追加到对应文档，不要另起分散文件。