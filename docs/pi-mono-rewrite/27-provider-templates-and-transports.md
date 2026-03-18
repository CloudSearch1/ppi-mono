# Provider 模板与传输层规范

这份文档补充 `ppi_ai/providers` 的 Python 重写方向，目标是把 provider 模板细化到足以直接开实现。

---

## 1. 目标

`ppi_ai/providers` 的职责是把不同模型供应商的请求和流式响应，统一收敛到 `ppi_ai` 的协议层。

现在 Python 侧已经有这些基础模块：

- `python/src/ppi_ai/providers/common.py`
- `python/src/ppi_ai/providers/base.py`
- `python/src/ppi_ai/providers/openai_completions.py`
- `python/src/ppi_ai/providers/openai_responses.py`
- `python/src/ppi_ai/providers/anthropic.py`

这次建议再补三个模板：

- `python/src/ppi_ai/providers/azure_openai_responses.py`
- `python/src/ppi_ai/providers/bedrock.py`
- `python/src/ppi_ai/providers/mistral.py`

---

## 2. 统一传输层

### 2.1 `HttpxProviderClient`

建议把所有 HTTP 访问收口到 `HttpxProviderClient`：

- `request()`
  - 单次非流式请求
  - 返回 `ProviderResponse`
- `stream()`
  - 返回 `httpx.AsyncClient.stream(...)`
  - 由 `ProviderAssistantMessageStream` 消费
- `close()`
  - 关闭共享 `AsyncClient`

### 2.2 provider stream 容器

`ProviderAssistantMessageStream` 应该维持这些能力：

- 可异步迭代事件
- 可单独 `result()`
- 可 `cancel()`
- 内部保存 `StreamParseState`

这保证 Python 侧和当前 JS 版本一样，可以把“事件消费”和“最终消息获取”分开。

---

## 3. 新 provider 模板

### 3.1 Azure OpenAI Responses

文件建议：

- [`python/src/ppi_ai/providers/azure_openai_responses.py`](../../python/src/ppi_ai/providers/azure_openai_responses.py)

职责：

- 复用 `openai_responses` 的消息转换与 chunk 解析
- 只覆盖 Azure 特有的 base URL、deployment name、api-version、`api-key` header

关键差异：

- endpoint 形式是 `.../deployments/{deployment}/responses?api-version=...`
- 认证 header 为 `api-key`
- deployment name 可能来自：
  - 显式 option
  - 环境变量映射
  - `model.id`

### 3.2 Bedrock

文件建议：

- [`python/src/ppi_ai/providers/bedrock.py`](../../python/src/ppi_ai/providers/bedrock.py)

职责：

- 封装 Bedrock Converse / ConverseStream 的 payload 结构
- 保留 tool / reasoning / content block 的映射模板

关键差异：

- Bedrock 不是 OpenAI-compatible
- 需要单独的 `messages/system/toolConfig/inferenceConfig` 形状
- 如果不引入签名 SDK，建议把它当成：
  - 代理后的 HTTP API 模板
  - 或未来签名 transport 的接口模板

### 3.3 Mistral

文件建议：

- [`python/src/ppi_ai/providers/mistral.py`](../../python/src/ppi_ai/providers/mistral.py)

职责：

- 基于 `chat/completions` 的 OpenAI-compatible 模板
- 复用 completions 的 payload 构造和 stream 解析

关键差异：

- base URL 默认应是 `https://api.mistral.ai/v1`
- tool call id / streaming arguments 需要保持兼容

---

## 4. 推荐导出

建议在 `python/src/ppi_ai/providers/__init__.py` 中导出：

- `AzureOpenAIResponsesProvider`
- `BedrockProvider`
- `MistralProvider`
- `HttpxProviderClient`

这样上层 registry 和测试代码可以直接导入具体 provider。

---

## 5. 兼容点

重写时最容易出问题的地方：

- tool call 的增量 JSON 拼装
- reasoning / thinking 片段的逐步输出
- `usage` 的聚合
- error 事件要带 partial assistant message
- `done` 和 `error` 都要保证消息可取

---

## 6. 实现建议

- OpenAI-compatible provider 用同一套 parse state
- Azure OpenAI 只改 endpoint 和 header
- Bedrock 单独适配 payload shape
- Mistral 优先复用 OpenAI completions 逻辑

