# `ppi_coding_agent` 持久化格式规范

这份文档把 `session / settings / model registry / resource loader / extensions` 的文件型实现收敛成可落地的读写 schema。

---

## 1. 总体约定

### 1.1 文件编码

- 所有 JSON / JSONL 文件统一使用 UTF-8
- JSON 输出建议 `indent=2`
- 语义上只追加不改写的结构尽量保持 append-only

### 1.2 版本字段

建议所有持久化文件至少保留一个版本字段：

- `session.jsonl` 的 header 记录里用 `version`
- `settings.json` 可保留顶层 `version`
- `model-registry.json` 可保留顶层 `version`

---

## 2. Session JSONL schema

文件建议路径：

- `.<cwd>/.ppi/sessions/<session_id>.jsonl`
- 或者由 `session_dir` 显式指定

### 2.1 第一行：session header

```json
{"type":"session","version":1,"id":"session_xxx","timestamp":"2026-03-19T12:00:00Z","cwd":"/work/project","parent_session":null}
```

字段说明：

- `type`
  - 固定为 `session`
- `version`
  - 格式版本
- `id`
  - session id
- `timestamp`
  - 创建时间
- `cwd`
  - session 关联工作目录
- `parent_session`
  - fork 来源 session，可为空

### 2.2 entry 行

每一行是一个 entry，至少包含：

- `type`
- `id`
- `parent_id`
- `timestamp`

#### message entry

```json
{
  "type": "message",
  "id": "message_1",
  "parent_id": "entry_0",
  "timestamp": "2026-03-19T12:01:00Z",
  "message": {
    "role": "user",
    "content": "hello",
    "timestamp": 0
  }
}
```

#### assistant message serialization

assistant message 建议序列化为：

- `role`
- `content`
- `api`
- `provider`
- `model`
- `response_id`
- `usage`
- `stop_reason`
- `error_message`
- `timestamp`

content block 目前支持：

- `text`
- `thinking`
- `toolCall`

#### tool result serialization

```json
{
  "type": "custom",
  "id": "entry_x",
  "parent_id": "entry_y",
  "timestamp": "...",
  "custom_type": "tool_result",
  "data": {
    "role": "toolResult",
    "tool_call_id": "...",
    "tool_name": "...",
    "content": []
  }
}
```

### 2.3 其他 entry 类型

建议保留这些类型：

- `compaction`
- `branch_summary`
- `custom`
- `custom_message`
- `label`
- `session_info`

### 2.4 读写规则

- `reload()` 需要重建 `entry_index` 和 `parent_index`
- `flush()` 需要覆盖整个文件
- `append_*()` 可以在 `autosave=True` 时自动写盘
- `fork_from()` 应保留原 session entries，再追加 fork 信息

---

## 3. Settings schema

文件建议路径：

- `settings.global.json`
- `settings.project.json`

### 3.1 顶层结构

```json
{
  "version": 1,
  "model": {},
  "thinking": {},
  "transport": {},
  "compaction": {},
  "retry": {},
  "terminal": {},
  "markdown": {},
  "resources": {},
  "extensions": {},
  "skills": {},
  "prompts": {},
  "themes": {},
  "packages": {}
}
```

### 3.2 合并规则

- project settings 覆盖 global settings
- dict 类型做深合并
- 其他类型按 project 优先

### 3.3 常用字段建议

`model`：

- `default`
- `provider`
- `reasoning`

`thinking`：

- `level`
- `budgets`

`transport`：

- `default`
- `proxy`

`markdown`：

- `block_images`

`resources`：

- `session_dir`
- `search_roots`

`extensions`：

- `enabled`
- `paths`

---

## 4. Model registry schema

文件建议路径：

- `model-registry.json`

### 4.1 顶层结构

```json
{
  "version": 1,
  "default_provider": "openai",
  "default_model_id": "gpt-5",
  "providers": {
    "openai": [
      {
        "provider": "openai",
        "api": "openai-responses",
        "id": "gpt-5",
        "name": "GPT-5",
        "base_url": "https://api.openai.com/v1",
        "reasoning": true,
        "input": ["text"],
        "output": ["text"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "compat": null
      }
    ]
  }
}
```

### 4.2 entry 字段

- `provider`
- `api`
- `id`
- `name`
- `base_url`
- `reasoning`
- `input`
- `output`
- `context_window`
- `max_output_tokens`
- `compat`

### 4.3 读写规则

- `register_provider()` 后可以自动保存
- `unregister_provider()` 后可以自动保存
- `resolve_default()` 优先使用 default provider/model
- 如果没有 default，回退到第一个可用模型

---

## 4.4 Provider registry schema

除了 `model-registry.json` 之外，Python 重写建议再支持一个更轻量的 provider 映射层，用来把逻辑 provider、具体 API 变体、`base_url`、`api_key` 显式绑定起来。

### 4.4.1 配置来源

推荐支持两种来源：

- 环境变量 `PI_PROVIDER_REGISTRY`
- 文件路径 `PI_PROVIDER_REGISTRY_FILE`

两者的内容都采用同一份 JSON 结构。

### 4.4.2 JSON 结构

```json
{
  "default": {
    "provider": "openai",
    "api": "openai-completions",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-..."
  },
  "routes": {
    "openai": {
      "provider": "openai",
      "api": "openai-completions",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-openai"
    },
    "openai:openai-responses": {
      "provider": "openai",
      "api": "openai-responses",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-openai-responses"
    },
    "vllm": {
      "provider": "openai",
      "api": "openai-completions",
      "base_url": "http://127.0.0.1:8000/v1",
      "api_key": "EMPTY"
    }
  }
}
```

### 4.4.3 路由规则

- 优先按 `provider:api` 精确匹配
- 其次按 `provider` 匹配
- 再其次按 `api` 匹配
- 最后回退到 `default`

### 4.4.4 推荐样例

#### OpenAI Completions

```json
{
  "routes": {
    "openai": {
      "provider": "openai",
      "api": "openai-completions",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-xxxxx"
    }
  }
}
```

#### OpenAI Responses

```json
{
  "routes": {
    "openai:openai-responses": {
      "provider": "openai",
      "api": "openai-responses",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-xxxxx"
    }
  }
}
```

#### vLLM / OpenAI-compatible

```json
{
  "routes": {
    "vllm": {
      "provider": "openai",
      "api": "openai-completions",
      "base_url": "http://127.0.0.1:8000/v1",
      "api_key": "EMPTY"
    }
  }
}
```

---

### 4.4.5 `PI_PROVIDER_REGISTRY_FILE` 路径约定

`PI_PROVIDER_REGISTRY_FILE` 建议只指向一个具体的 JSON 文件，而不是目录。

推荐约定：

- 文件必须是 UTF-8 编码的纯 JSON
- 文件内容与 `PI_PROVIDER_REGISTRY` 的 JSON 结构完全一致
- 允许使用绝对路径或相对路径
- 相对路径建议按当前工作目录解析，或显式绑定到项目配置目录
- 推荐命名：
  - `~/.pi/provider-registry.json`
  - `.<cwd>/.ppi/provider-registry.json`
  - `<project-root>/.pi/provider-registry.json`

建议优先级：

1. 显式传入的文件路径
2. `PI_PROVIDER_REGISTRY_FILE`
3. `PI_PROVIDER_REGISTRY`

如果同时存在环境变量和文件，建议文件优先，便于本地覆盖和项目级固定配置。

### 4.4.6 `.json` 文件示例

示例文件见 `examples/provider-registry.json`。

```json
{
  "default": {
    "provider": "openai",
    "api": "openai-completions",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-openai"
  },
  "routes": {
    "openai": {
      "provider": "openai",
      "api": "openai-completions",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-openai"
    },
    "openai:openai-responses": {
      "provider": "openai",
      "api": "openai-responses",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-openai-responses"
    },
    "vllm": {
      "provider": "openai",
      "api": "openai-completions",
      "base_url": "http://127.0.0.1:8000/v1",
      "api_key": "EMPTY"
    }
  }
}
```

---

## 5. Resource manifest schema

建议资源清单采用 JSON 读写，便于测试和重放。

顶层建议：

```json
{
  "resources": {
    "skill": [],
    "prompt": [],
    "theme": [],
    "extension": [],
    "agent": [],
    "package": [],
    "config": []
  },
  "diagnostics": [],
  "collisions": []
}
```

资源项：

- `kind`
- `path`
- `name`
- `source`
- `metadata`

---

## 6. Extension manifest schema

建议路径：

- `extensions.json`

结构：

```json
{
  "extensions": [
    {
      "name": "example-tool",
      "kind": "tool",
      "path": "extensions/example-tool.py",
      "metadata": {}
    }
  ]
}
```

---

## 7. Implementation notes

- `InMemory*` 实现适合测试和无文件场景
- `File*` 实现负责 JSON / JSONL 持久化
- `reload()` 应该成为从磁盘恢复状态的唯一入口
- 写盘前尽量先转换成纯 dict，避免直接依赖 dataclass 内部结构
