# `pi-tui` 与 `pi-web-ui` 设计分析

## 1. 模块职责与边界

### `pi-tui`

`pi-tui` 是终端交互内核，不是简单组件集合。它负责：

- 终端能力探测和输入归一化
- 键盘序列解析，包括 Kitty protocol、xterm `modifyOtherKeys`、bracketed paste
- 差异渲染和 synchronized output
- overlay / modal 叠层
- hardware cursor 和 IME 定位
- 基础组件：`Input`、`Editor`、`SelectList`、`Markdown`、`Loader`、`Image`

关键入口：

- [`packages/tui/src/tui.ts`](../../packages/tui/src/tui.ts#L209)
- [`packages/tui/src/terminal.ts`](../../packages/tui/src/terminal.ts#L55)
- [`packages/tui/src/keys.ts`](../../packages/tui/src/keys.ts#L228)
- [`packages/tui/src/components/editor.ts`](../../packages/tui/src/components/editor.ts#L215)

### `pi-web-ui`

`pi-web-ui` 是浏览器侧 chat runtime 和可复用 UI 层。它负责：

- ChatPanel 布局编排
- Agent 事件订阅与消息渲染
- 附件解析和上传
- IndexedDB 会话/设置/密钥存储
- artifact 面板和 sandbox 执行
- 工具渲染注册
- 自定义消息类型和消息到 LLM 的转换

关键入口：

- [`packages/web-ui/src/ChatPanel.ts`](../../packages/web-ui/src/ChatPanel.ts#L18)
- [`packages/web-ui/src/components/AgentInterface.ts`](../../packages/web-ui/src/components/AgentInterface.ts#L20)
- [`packages/web-ui/src/components/Messages.ts`](../../packages/web-ui/src/components/Messages.ts#L18)
- [`packages/web-ui/src/tools/artifacts/artifacts.ts`](../../packages/web-ui/src/tools/artifacts/artifacts.ts#L54)

## 2. `pi-tui` 架构

### 渲染模型

`TUI` 继承 `Container`，所有子组件都遵守统一协议：

- `render(width) -> string[]`
- `handleInput?(data)`
- `invalidate()`

渲染时先把整棵树渲成行数组，再做行级 diff。差异渲染有三种路径：

- 首次渲染，直接输出整屏
- 宽高变化，强制全量重绘
- 普通更新，定位到首个变化行后只重绘局部

overlay 是单独的栈，按 `focusOrder` 叠加到基础内容上，支持：

- `width/maxHeight` 的绝对值和百分比
- `row/col` 的绝对值、百分比或 anchor
- `visible` 动态可见性
- `nonCapturing` 非抢占焦点

参考实现：

- [`packages/tui/src/tui.ts`](../../packages/tui/src/tui.ts#L297)
- [`packages/tui/src/tui.ts`](../../packages/tui/src/tui.ts#L717)
- [`packages/tui/src/tui.ts`](../../packages/tui/src/tui.ts#L869)

### 输入模型

输入不是普通 keydown，而是 terminal-sequence 级别处理：

- Kitty keyboard protocol
- xterm `modifyOtherKeys`
- legacy escape sequences
- bracketed paste
- key release / repeat

`ProcessTerminal` 负责 raw mode、VT 输入、Kitty protocol 探测，以及把 stdin 切分成完整序列；`StdinBuffer` 负责把分片的 escape sequence 合并后再交给上层。

参考实现：

- [`packages/tui/src/terminal.ts`](../../packages/tui/src/terminal.ts#L55)
- [`packages/tui/src/stdin-buffer.ts`](../../packages/tui/src/stdin-buffer.ts)
- [`packages/tui/src/keys.ts`](../../packages/tui/src/keys.ts#L228)

### 输入控件

`Input` 和 `Editor` 都是状态型组件，但仍遵循 `Component` 接口。它们共同依赖：

- `Intl.Segmenter`，按 grapheme 处理光标移动和删除
- bracketed paste
- kill ring / undo
- `CURSOR_MARKER` 做 hardware cursor 定位

`Editor` 额外支持：

- history
- vertical scroll
- slash command autocomplete
- file path autocomplete

参考实现：

- [`packages/tui/src/components/input.ts`](../../packages/tui/src/components/input.ts#L18)
- [`packages/tui/src/components/editor.ts`](../../packages/tui/src/components/editor.ts#L215)
- [`packages/tui/src/editor-component.ts`](../../packages/tui/src/editor-component.ts#L11)

### 内置组件

- `SelectList` 提供过滤、选中、滚动和主题化渲染，适合命令菜单和文件选择器。
- `Markdown` 负责把 markdown 解析成终端可渲染行，并做 ANSI 安全 wrap。
- `Loader` 是一个自动刷新帧的文本 spinner。

参考实现：

- [`packages/tui/src/components/select-list.ts`](../../packages/tui/src/components/select-list.ts#L40)
- [`packages/tui/src/components/markdown.ts`](../../packages/tui/src/components/markdown.ts#L54)
- [`packages/tui/src/components/loader.ts`](../../packages/tui/src/components/loader.ts#L7)

## 3. `pi-web-ui` 架构

### 主视图

`ChatPanel` 只是布局壳。它把：

- `AgentInterface`
- `ArtifactsPanel`
- runtime provider factory
- tool registration

组合在一起，并在移动端切成 overlay 模式。

`AgentInterface` 才是核心：它订阅 `Agent` 事件，维护稳定消息列表和 streaming 消息容器，处理发送、abort、model selector、thinking selector、成本展示和自动滚动。

参考实现：

- [`packages/web-ui/src/ChatPanel.ts`](../../packages/web-ui/src/ChatPanel.ts#L56)
- [`packages/web-ui/src/components/AgentInterface.ts`](../../packages/web-ui/src/components/AgentInterface.ts#L130)
- [`packages/web-ui/src/components/MessageList.ts`](../../packages/web-ui/src/components/MessageList.ts#L11)
- [`packages/web-ui/src/components/StreamingMessageContainer.ts`](../../packages/web-ui/src/components/StreamingMessageContainer.ts#L6)

### 消息模型

`Messages.ts` 定义了 web 层扩展消息：

- `user-with-attachments`
- `artifact`

`defaultConvertToLlm()` 会：

- 过滤 artifact 消息
- 把附件转换成 image/text content blocks
- 保留标准 `user/assistant/toolResult`

这个设计很重要，因为它把 UI 内部状态和 LLM 可见上下文明确分开了。

参考实现：

- [`packages/web-ui/src/components/Messages.ts`](../../packages/web-ui/src/components/Messages.ts#L18)
- [`packages/web-ui/src/components/Messages.ts`](../../packages/web-ui/src/components/Messages.ts#L348)
- [`packages/web-ui/src/components/message-renderer-registry.ts`](../../packages/web-ui/src/components/message-renderer-registry.ts#L1)

### Streaming 处理

`MessageList` 渲染稳定历史消息，`StreamingMessageContainer` 只负责当前增量消息。后者用 `requestAnimationFrame` 批处理更新，并深拷贝 message，避免 Lit 不响应嵌套字段变化。

Python 重写时可以保留“双层渲染”的思想，但不必复刻 Lit 的内部技巧。

### Storage

`web-ui` 的 storage 是多 store 抽象，不是简单 localStorage：

- `settings`
- `provider-keys`
- `sessions`
- `sessions-metadata`
- `custom-providers`

`SessionsStore` 采用双表设计，full session 和 metadata 分离；metadata 支持按 `lastModified` 排序查询。

参考实现：

- [`packages/web-ui/src/storage/types.ts`](../../packages/web-ui/src/storage/types.ts#L29)
- [`packages/web-ui/src/storage/stores/sessions-store.ts`](../../packages/web-ui/src/storage/stores/sessions-store.ts#L9)
- [`packages/web-ui/src/storage/backends/indexeddb-storage-backend.ts`](../../packages/web-ui/src/storage/backends/indexeddb-storage-backend.ts#L7)

### Attachments

`loadAttachment()` 支持：

- `File / Blob / ArrayBuffer / URL`
- PDF、DOCX、PPTX、Excel、图片、文本
- base64 原始内容
- 文档抽取文本和预览图

对 Python 重写来说，这部分建议独立成文档处理模块，不要绑在 UI 上。

参考实现：

- [`packages/web-ui/src/utils/attachment-utils.ts`](../../packages/web-ui/src/utils/attachment-utils.ts#L29)

### Tools 与 sandbox

`ArtifactsPanel` 是一个真正的 `AgentTool`，并且把 artifact 操作映射成可重放消息。`ArtifactsRuntimeProvider` 和 `AttachmentsRuntimeProvider` 则把 artifact/attachment 状态暴露给 sandbox 里的 JS。

`SandboxIframe` 做了三件事：

- 生成可注入的 runtime bridge
- 校验 HTML
- 管理 iframe 生命周期和消息路由

参考实现：

- [`packages/web-ui/src/tools/artifacts/artifacts.ts`](../../packages/web-ui/src/tools/artifacts/artifacts.ts#L272)
- [`packages/web-ui/src/components/sandbox/ArtifactsRuntimeProvider.ts`](../../packages/web-ui/src/components/sandbox/ArtifactsRuntimeProvider.ts#L26)
- [`packages/web-ui/src/components/sandbox/AttachmentsRuntimeProvider.ts`](../../packages/web-ui/src/components/sandbox/AttachmentsRuntimeProvider.ts#L12)
- [`packages/web-ui/src/components/SandboxedIframe.ts`](../../packages/web-ui/src/components/SandboxedIframe.ts#L48)

## 4. Python 重写建议

### `pi-tui`

推荐优先级：

1. `Textual` 做主壳、列表、modal、overlay、消息流。
2. `prompt_toolkit` 处理高 fidelity 输入控件，尤其是 editor / autocomplete。
3. 自己保留一个轻量 terminal codec 层，负责按键序列归一化和 bracketed paste。

必须保留的语义：

- 行级 diff 渲染
- 宽字符/ANSI 安全裁剪
- overlay 叠层
- IME hardware cursor
- Kitty / modifyOtherKeys / bracketed paste 支持

### `pi-web-ui`

推荐用 `FastAPI` + 前端 SPA，而不是纯 HTMX。原因很直接：当前 UI 依赖：

- 流式增量消息
- artifact sandbox
- 双向 runtime bridge
- 文档附件预览
- tool renderer registry

HTMX 可以做简单 chat，但很难保留这些能力的结构化交互。

推荐拆分：

- `web_core`: 消息模型、storage、attachments、artifact state
- `web_api`: SSE/WebSocket、session、auth、provider key
- `web_frontend`: 聊天界面、artifact 面板、sandbox iframe

### 数据层

建议 Python 直接对齐这些模型：

- `AgentMessage`
- `AssistantMessage`
- `ToolCall`
- `ToolResult`
- `Attachment`
- `SessionData`
- `SessionMetadata`
- `ArtifactMessage`

存储层建议使用事务明确的后端：

- 本地桌面版：SQLite
- 服务端版：Postgres + SQLAlchemy

### 设计风险

- 如果终端输入不支持 Kitty / modifyOtherKeys，编辑器快捷键会明显退化。
- 如果 web 侧没有“稳定列表 + streaming 层”分离，渲染抖动会很重。
- 如果 artifact 不是可重放消息，session 回放和 branch 会变难。
- 如果 storage 不保留 metadata/full-session 分层，列表页性能会差。

