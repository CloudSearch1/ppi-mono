# pi-mono 重写设计稿

这是对 `pi-mono` 的结构化分析，目标是为后续用 Python 重写提供可执行的设计基线。

## 文档索引

- [01-ai-agent-design.md](./01-ai-agent-design.md)
- [02-coding-agent-architecture.md](./02-coding-agent-architecture.md)
- [03-python-rewrite-plan.md](./03-python-rewrite-plan.md)
- [04-coding-agent-core.md](./04-coding-agent-core.md)
- [05-ui-design.md](./05-ui-design.md)
- [06-agent-coding-agent-design.md](./06-agent-coding-agent-design.md)
- [07-python-package-layout.md](./07-python-package-layout.md)
- [08-coding-agent-implementation-matrix.md](./08-coding-agent-implementation-matrix.md)
- [09-python-package-structure.md](./09-python-package-structure.md)
- [10-coding-agent-core-call-flow.md](./10-coding-agent-core-call-flow.md)
- [12-pi-cli-mode-sequence.md](./12-pi-cli-mode-sequence.md)
- [11-pimono-ai-protocol-draft.md](./11-pimono-ai-protocol-draft.md)
- [13-python-protocols-and-dataclasses.md](./13-python-protocols-and-dataclasses.md)
- [16-python-package-structure-files.md](./16-python-package-structure-files.md)
- [17-mom-pods-protocols.md](./17-mom-pods-protocols.md)
- [18-pimono-ai-code-skeleton.md](./18-pimono-ai-code-skeleton.md)
- [19-pimono-agent-core-interface.md](./19-pimono-agent-core-interface.md)
- [20-pimono-ai-code-templates.md](./20-pimono-ai-code-templates.md)
- [21-pimono-coding-agent-interface-draft.md](./21-pimono-coding-agent-interface-draft.md)
- [22-mom-message-file-scheduler-sequence.md](./22-mom-message-file-scheduler-sequence.md)
- [23-pods-command-sequences.md](./23-pods-command-sequences.md)
- [24-mom-pods-python-package-skeleton.md](./24-mom-pods-python-package-skeleton.md)
- [25-mom-pods-python-protocols.md](./25-mom-pods-python-protocols.md)
- [26-ppi-ai-reuse-mapping.md](./26-ppi-ai-reuse-mapping.md)
- [27-provider-templates-and-transports.md](./27-provider-templates-and-transports.md)
- [28-coding-agent-persistence-schemas.md](./28-coding-agent-persistence-schemas.md)
- [29-mom-pods-design.md](./29-mom-pods-design.md)
- [16-python-implementation-task-breakdown.md](./16-python-implementation-task-breakdown.md)

## 说明

- 这里的内容基于仓库内 README 和源码阅读，不依赖外部推测。
- 重点关注三个层次：`pi-ai` 协议层、`pi-agent-core` 编排层、`pi-coding-agent` 产品层。
- 后续如果继续补充分析，优先追加到对应文档，不要另起分散文件。
