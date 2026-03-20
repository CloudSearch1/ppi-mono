# Python Rewrite Design: `mom` + `pods`

This document summarizes the current TypeScript implementation of `packages/mom` and `packages/pods`, and turns it into a Python-oriented design target.

## 1. Module Responsibilities

### `mom`

`mom` is a Slack-driven agent runtime. It receives Slack events, persists channel history, syncs context, runs the coding agent, executes tools inside a sandbox, and posts results back to Slack.

Primary users:
- Developers who want to delegate work from Slack
- Teams that want a persistent conversational assistant with file and shell access
- Users who need scheduled reminders or external event triggers

### `pods`

`pods` is a remote GPU pod management CLI. It prepares Ubuntu GPU machines for vLLM, manages local pod configuration, starts/stops model servers over SSH, and exposes OpenAI-compatible endpoints.

Primary users:
- ML engineers running agentic models on GPU pods
- Developers who want a lightweight model-serving control plane
- Users who need repeatable model bootstrapping on remote machines

## 2. Current Architecture

### `mom`

The runtime is layered as:

`Slack event -> per-channel queue -> AgentRunner -> AgentSession -> tools -> sandbox executor -> Slack response`

Key layers:
- Slack adapter: event ingestion, message posting, thread replies, file upload
- Channel state: one runner and one store per channel
- Context management: `log.jsonl` sync into `context.jsonl`
- Agent execution: `pi-agent-core` session + `pi-coding-agent` wrapper
- Tool execution: `read`, `bash`, `edit`, `write`, `attach`
- Sandbox: host or Docker execution
- Event scheduler: JSON-file based immediate / one-shot / periodic triggers

### `pods`

The runtime is:

`CLI -> local config -> SSH/SCP -> remote bootstrap script -> vLLM process -> local state update`

Key layers:
- CLI command parsing
- Local persistent config in `~/.pi/pods.json`
- SSH execution helper
- Model registry / hardware compatibility rules
- Remote setup script generation and execution
- Remote vLLM process supervision via PID + log files

## 3. Core Interfaces

### `mom`

Important data shapes:
- `SlackEvent`
- `SlackContext`
- `MomEvent` with `immediate`, `one-shot`, `periodic`
- `SandboxConfig`
- `Executor`
- `Attachment`
- `LoggedMessage`
- `AgentRunner`

Important filesystem contracts:
- `context.jsonl`: structured LLM context
- `log.jsonl`: human-readable channel history
- `attachments/`: downloaded Slack files
- `MEMORY.md`: workspace and channel memory
- `events/*.json`: scheduled event definitions

Important command / behavior contracts:
- `@mom` mentions in channels
- DMs to the bot
- `stop` command
- event file execution
- silent completion via `[SILENT]`

### `pods`

Important data shapes:
- `GPU`
- `Model`
- `Pod`
- `Config`

Important CLI commands:
- `pi pods setup`
- `pi pods`
- `pi pods active`
- `pi pods remove`
- `pi start`
- `pi stop`
- `pi list`
- `pi logs`
- `pi agent`

Important runtime files:
- `~/.pi/pods.json`
- remote `~/.vllm_logs/<name>.log`
- remote `~/venv`
- remote `~/.cache/huggingface`

## 4. External Integrations

### Slack

`mom` uses:
- Socket Mode for event ingestion
- Web API for message posting, updates, deletes, thread replies, and file upload
- Slack conversation history for backfill

Important Slack event paths:
- `app_mention`
- `message`
- DMs
- file uploads

### SSH

`pods` uses SSH for:
- pod bootstrap
- command execution
- log tailing
- process termination
- model deployment

`mom` also can execute commands inside a Docker container through local shell / `docker exec`.

### Docker

`mom` supports:
- host execution
- Docker sandbox execution

Docker mode is the safer default when the bot has access to Slack and workspace data.

### vLLM

`pods` is tightly coupled to vLLM deployment conventions:
- `vllm serve`
- model-specific tool parsers
- reasoning parsers
- tensor / data parallel settings
- model-specific env vars
- health endpoint checks

The model registry is data-driven through `models.json`.

## 5. Python Rewrite Recommendation

### Suggested package split

#### For `mom`

- `mom_core`
  - agent orchestration
  - session handling
  - tool dispatch
  - context sync
- `mom_platforms.slack`
  - Slack adapter
  - event mapping
  - message formatting
- `mom_storage`
  - JSONL persistence
  - memory files
  - attachment downloads
- `mom_scheduler`
  - file-based event watcher
  - cron scheduling
  - one-shot timers
- `mom_sandbox`
  - host executor
  - Docker executor

#### For `pods`

- `pods_cli`
  - CLI entrypoint
  - argument parsing
- `pods_store`
  - local config persistence
- `pods_ssh`
  - SSH / SCP / streaming execution
- `pods_setup`
  - remote bootstrap
  - pod detection
- `pods_models`
  - model registry
  - compatibility rules
- `pods_runtime`
  - start / stop / list / logs

### Python implementation choices

Recommended primitives:
- `asyncio` for orchestration
- `pydantic` for typed configs and events
- `watchdog` for filesystem watching
- `APScheduler` or `croniter` for schedules
- `paramiko` or subprocess-based `ssh` for remote commands
- `slack_bolt` or `slack_sdk` for Slack
- `subprocess` plus explicit process groups for local execution

### Compatibility priorities

Preserve these behaviors first:
- per-channel isolation
- persistent context sync
- attachment handling
- thread replies and long response splitting
- event file semantics
- model selection by hardware capability
- remote process tracking by PID and log tailing

### Optional simplifications

Potentially simplify:
- hardcoded console formatting
- some of the richer log decoration
- TypeScript-specific SDK wrapping
- duplicated prompt text generation paths

## 6. Main Risks

### `mom`

- Slack-specific concepts are currently embedded in the runtime
- The bot has full workspace and shell access, so prompt injection is a real security risk
- Context/log divergence can happen if sync logic is changed incorrectly
- Docker sandboxing is safer but still does not solve credential exfiltration

### `pods`

- Local config can drift from remote reality if a pod reboots or a process is killed manually
- Model-specific vLLM tuning is highly sensitive to hardware and engine version
- The current code mixes orchestration logic and remote shell scripts
- `pi agent` / `prompt` is not fully implemented in the current codebase

## 7. Recommended Migration Order

1. Recreate `pods` as a Python CLI with the same local config format and SSH execution model.
2. Recreate `mom` with a platform-agnostic core and a Slack adapter on top.
3. Keep remote bootstrap and model launch scripts as shell templates initially, then move only the orchestration layer to Python.
4. Add adapter-agnostic test fixtures for events, context sync, and tool execution.

## 8. Concrete File References

- `packages/mom/src/main.ts`
- `packages/mom/src/agent.ts`
- `packages/mom/src/slack.ts`
- `packages/mom/src/context.ts`
- `packages/mom/src/events.ts`
- `packages/mom/src/sandbox.ts`
- `packages/mom/src/store.ts`
- `packages/pods/src/cli.ts`
- `packages/pods/src/commands/models.ts`
- `packages/pods/src/commands/pods.ts`
- `packages/pods/src/model-configs.ts`
- `packages/pods/src/ssh.ts`
- `packages/pods/scripts/pod_setup.sh`
- `packages/pods/scripts/model_run.sh`
- `packages/pods/docs/implementation-plan.md`
- `packages/pods/docs/models.md`
- `packages/pods/docs/gpt-oss.md`
- `packages/pods/docs/gml-4.5.md`
- `packages/pods/docs/qwen3-coder.md`
- `packages/pods/docs/kimi-k2.md`
