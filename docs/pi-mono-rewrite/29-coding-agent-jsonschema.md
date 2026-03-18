# `ppi_coding_agent` JSON Schema 文档

这份文档把 `session / settings / model registry` 的文件格式整理成可以直接用于校验的 JSON Schema。
对应的可加载文件已经拆到 `python/schemas/coding-agent/*.schema.json`，并由 `schema-registry.json` 统一管理。

---

## 1. Session JSONL

`session` 文件是 JSONL：

- 第 1 行是 session header
- 后续每一行是一个 entry

### 1.1 Session header schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pi-mono.local/schema/session-header.json",
  "title": "SessionHeader",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "version", "id", "timestamp", "cwd"],
  "properties": {
    "type": { "const": "session" },
    "version": { "type": "integer", "minimum": 1 },
    "id": { "type": "string", "minLength": 1 },
    "timestamp": { "type": "string", "minLength": 1 },
    "cwd": { "type": "string" },
    "parent_session": { "type": ["string", "null"] }
  }
}
```

### 1.2 Session entry schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pi-mono.local/schema/session-entry.json",
  "title": "SessionEntry",
  "oneOf": [
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "id", "timestamp"],
      "properties": {
        "type": { "const": "message" },
        "id": { "type": "string", "minLength": 1 },
        "parent_id": { "type": ["string", "null"] },
        "timestamp": { "type": "string", "minLength": 1 },
        "message": {
          "oneOf": [
            { "type": "null" },
            { "$ref": "#/$defs/message" }
          ]
        }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "id", "timestamp", "summary", "first_kept_entry_id", "tokens_before"],
      "properties": {
        "type": { "const": "compaction" },
        "id": { "type": "string", "minLength": 1 },
        "parent_id": { "type": ["string", "null"] },
        "timestamp": { "type": "string", "minLength": 1 },
        "summary": { "type": "string" },
        "first_kept_entry_id": { "type": "string" },
        "tokens_before": { "type": "integer", "minimum": 0 },
        "details": { "type": "object", "additionalProperties": true }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "id", "timestamp", "summary"],
      "properties": {
        "type": { "const": "branch_summary" },
        "id": { "type": "string", "minLength": 1 },
        "parent_id": { "type": ["string", "null"] },
        "timestamp": { "type": "string", "minLength": 1 },
        "summary": { "type": "string" },
        "details": { "type": "object", "additionalProperties": true }
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "id", "timestamp", "custom_type"],
      "properties": {
        "type": { "enum": ["custom", "custom_message"] },
        "id": { "type": "string", "minLength": 1 },
        "parent_id": { "type": ["string", "null"] },
        "timestamp": { "type": "string", "minLength": 1 },
        "custom_type": { "type": "string", "minLength": 1 },
        "data": {},
        "content": {},
        "display": { "type": "boolean" },
        "details": {}
      }
    },
    {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "id", "timestamp"],
      "properties": {
        "type": { "enum": ["label", "session_info"] },
        "id": { "type": "string", "minLength": 1 },
        "parent_id": { "type": ["string", "null"] },
        "timestamp": { "type": "string", "minLength": 1 },
        "label": { "type": ["string", "null"] },
        "name": { "type": "string" }
      }
    }
  ],
  "$defs": {
    "message": {
      "oneOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["role", "content", "timestamp"],
          "properties": {
            "role": { "const": "user" },
            "content": {
              "oneOf": [
                { "type": "string" },
                {
                  "type": "array",
                  "items": { "$ref": "#/$defs/contentBlock" }
                }
              ]
            },
            "timestamp": { "type": "integer" }
          }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["role", "content", "api", "provider", "model", "stop_reason", "timestamp"],
          "properties": {
            "role": { "const": "assistant" },
            "content": {
              "type": "array",
              "items": { "$ref": "#/$defs/contentBlock" }
            },
            "api": { "type": "string" },
            "provider": { "type": "string" },
            "model": { "type": "string" },
            "response_id": { "type": ["string", "null"] },
            "usage": { "$ref": "#/$defs/usage" },
            "stop_reason": { "type": "string" },
            "error_message": { "type": ["string", "null"] },
            "timestamp": { "type": "integer" }
          }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["role", "tool_call_id", "tool_name", "content", "timestamp"],
          "properties": {
            "role": { "const": "toolResult" },
            "tool_call_id": { "type": "string" },
            "tool_name": { "type": "string" },
            "content": {
              "type": "array",
              "items": { "$ref": "#/$defs/contentBlock" }
            },
            "details": { "type": "object", "additionalProperties": true },
            "is_error": { "type": "boolean" },
            "timestamp": { "type": "integer" }
          }
        }
      ]
    },
    "contentBlock": {
      "oneOf": [
        {
          "type": "object",
          "required": ["type", "text"],
          "additionalProperties": true,
          "properties": {
            "type": { "const": "text" },
            "text": { "type": "string" },
            "text_signature": { "type": ["string", "null"] }
          }
        },
        {
          "type": "object",
          "required": ["type", "thinking"],
          "additionalProperties": true,
          "properties": {
            "type": { "const": "thinking" },
            "thinking": { "type": "string" },
            "thinking_signature": { "type": ["string", "null"] },
            "redacted": { "type": "boolean" }
          }
        },
        {
          "type": "object",
          "required": ["type", "id", "name", "arguments"],
          "additionalProperties": true,
          "properties": {
            "type": { "const": "toolCall" },
            "id": { "type": "string" },
            "name": { "type": "string" },
            "arguments": { "type": "object", "additionalProperties": true },
            "thought_signature": { "type": ["string", "null"] }
          }
        },
        {
          "type": "object",
          "required": ["type", "data"],
          "additionalProperties": true,
          "properties": {
            "type": { "const": "image" },
            "data": { "type": "string" },
            "mime_type": { "type": "string" }
          }
        }
      ]
    },
    "usage": {
      "type": "object",
      "additionalProperties": false,
      "required": ["input", "output", "cache_read", "cache_write", "total_tokens"],
      "properties": {
        "input": { "type": "integer", "minimum": 0 },
        "output": { "type": "integer", "minimum": 0 },
        "cache_read": { "type": "integer", "minimum": 0 },
        "cache_write": { "type": "integer", "minimum": 0 },
        "total_tokens": { "type": "integer", "minimum": 0 },
        "cost": { "type": "object", "additionalProperties": { "type": "number" } }
      }
    }
  }
}
```

---

## 2. Settings schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pi-mono.local/schema/settings.json",
  "title": "Settings",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "model", "thinking", "transport", "compaction", "retry", "terminal", "markdown", "resources", "extensions", "skills", "prompts", "themes", "packages"],
  "properties": {
    "version": { "type": "integer", "minimum": 1 },
    "model": { "type": "object", "additionalProperties": true },
    "thinking": { "type": "object", "additionalProperties": true },
    "transport": { "type": "object", "additionalProperties": true },
    "compaction": { "type": "object", "additionalProperties": true },
    "retry": { "type": "object", "additionalProperties": true },
    "terminal": { "type": "object", "additionalProperties": true },
    "markdown": { "type": "object", "additionalProperties": true },
    "resources": { "type": "object", "additionalProperties": true },
    "extensions": { "type": "object", "additionalProperties": true },
    "skills": { "type": "object", "additionalProperties": true },
    "prompts": { "type": "object", "additionalProperties": true },
    "themes": { "type": "object", "additionalProperties": true },
    "packages": { "type": "object", "additionalProperties": true }
  }
}
```

---

## 3. Model registry schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://pi-mono.local/schema/model-registry.json",
  "title": "ModelRegistry",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "providers"],
  "properties": {
    "version": { "type": "integer", "minimum": 1 },
    "default_provider": { "type": ["string", "null"] },
    "default_model_id": { "type": ["string", "null"] },
    "providers": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["provider", "api", "id"],
          "properties": {
            "provider": { "type": "string" },
            "api": { "type": "string" },
            "id": { "type": "string" },
            "name": { "type": ["string", "null"] },
            "base_url": { "type": ["string", "null"] },
            "reasoning": { "type": "boolean" },
            "input": {
              "type": "array",
              "items": { "type": "string" }
            },
            "output": {
              "type": "array",
              "items": { "type": "string" }
            },
            "context_window": { "type": ["integer", "null"] },
            "max_output_tokens": { "type": ["integer", "null"] },
            "compat": { "type": ["object", "null"], "additionalProperties": true }
          }
        }
      }
    }
  }
}
```

---

## 4. Validation guidance

- `session.jsonl`
  - 先校验 header
  - 后续每行按 entry union 校验
- `settings.json`
  - 直接按单个 schema 校验
- `model-registry.json`
  - 直接按单个 schema 校验
