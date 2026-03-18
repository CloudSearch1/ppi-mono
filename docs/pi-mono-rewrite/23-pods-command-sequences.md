# `pods` 命令执行时序图

这份文档把 `packages/pods` 的五条关键命令拆开说明：

- `setup`
- `start`
- `stop`
- `logs`
- `agent`

目标是帮助 Python 重写时保留它的真实行为边界，而不是只复刻 CLI 文案。

---

## 1. 模块职责

`pods` 不是单纯的部署脚本封装，它更像一个本地控制面：

- 管理本地 pod 配置
- 通过 SSH/SCP 操作远端 GPU 节点
- 安装和初始化运行环境
- 启动 / 停止 vLLM 实例
- 维护 model -> port -> pid -> gpu 的本地状态
- 给 agent 提供 OpenAI-compatible endpoint 元数据

它的状态源是本地配置文件，而不是远端主机。

---

## 2. 公共前置依赖

所有命令都共享这些基础组件：

- `loadConfig()` / `saveConfig()`：本地配置读写
- `getActivePod()`：确定当前活跃 pod
- `sshExec()` / `sshExecStream()`：远端命令执行
- `scpFile()`：脚本上传
- `model-configs.ts`：模型与 GPU 兼容性矩阵
- `types.ts`：`Pod` / `GPU` / `Model` / `Config`

---

## 3. `setup` 时序

### 3.1 目标

`setup` 用于把一个新的远端机器变成可用 pod。

### 3.2 执行步骤

```text
pi pods setup
  -> validate HF_TOKEN / PI_API_KEY
  -> resolve modelsPath
  -> sshExec("echo SSH OK")
  -> scpFile(pod_setup.sh -> /tmp/pod_setup.sh)
  -> sshExecStream("bash /tmp/pod_setup.sh ...", forceTTY=true)
  -> sshExec("nvidia-smi ...")
  -> build Pod config
  -> addPod(name, pod)
```

### 3.3 关键语义

- 先验证环境变量，再做远程操作
- `--mount` 可推导 `modelsPath`
- setup 脚本是远端 bootstrap 的核心
- GPU 探测在 setup 完成后执行
- setup 结果写入本地 config，并自动成为 active pod

### 3.4 失败点

- 缺 `HF_TOKEN` 或 `PI_API_KEY` 直接退出
- SSH 不通直接退出
- setup script 复制失败直接退出
- 远端脚本失败直接退出
- `nvidia-smi` 不可用时会得到空 GPU 列表，但 pod 仍可能被保存

---

## 4. `start` 时序

### 4.1 目标

`start` 负责在指定 pod 上启动一个 vLLM 模型实例，并把结果写回本地状态。

### 4.2 执行步骤

```text
pi start <model> --name <name>
  -> getPod(active or override)
  -> validate pod.modelsPath
  -> validate model name uniqueness
  -> compute port
  -> select model config / GPUs / vLLM args
  -> customize model_run.sh
  -> sshExec("cat > /tmp/model_run_...sh")
  -> sshExec(startCmd with setsid + script)
  -> parse PID
  -> save config with model metadata
  -> tail remote log
  -> detect startup success/failure
  -> adjust config if failed
```

### 4.3 关键语义

- `model_run.sh` 是远端启动模板
- `script -q -f -c` 用来保留颜色和生成日志文件
- `setsid` 让模型脱离 SSH 会话继续运行
- 本地 config 保存的是“事实上的运行状态”
- 启动成功后会输出 OpenAI-compatible base url 和环境变量

### 4.4 成功判定

成功的主要标志是日志出现：

- `Application startup complete`

失败判定包括：

- `Model runner exiting with code`
- `Script exited with code`
- `torch.OutOfMemoryError`
- `CUDA out of memory`
- `RuntimeError: Engine core initialization failed`

### 4.5 失败处理

- 启动失败会删除本地 config 中的模型条目
- OOM 会给出 memory/context/quantization 方面的建议
- 日志 tail 可以被 Ctrl+C 中断，但模型本身继续在远端运行

---

## 5. `stop` 时序

### 5.1 目标

`stop` 用于关闭单个模型或当前 pod 上的全部模型。

### 5.2 单模型

```text
pi stop <name>
  -> getPod()
  -> lookup model in pod.models
  -> sshExec("pkill -TERM -P pid; kill pid")
  -> delete model from config
```

### 5.3 全量停止

```text
pi stop
  -> getPod()
  -> enumerate pod.models
  -> sshExec("for PID in ...; do ...; done")
  -> clear pod.models
  -> saveConfig()
```

### 5.4 关键语义

- stop 的真实对象是远端 process tree
- 本地 config 会同步清理
- 没有引入复杂的 grace period 或 checkpoint 机制

---

## 6. `logs` 时序

### 6.1 目标

`logs` 只是把远端 `~/.vllm_logs/<name>.log` 透传到本地终端。

### 6.2 执行步骤

```text
pi logs <name>
  -> getPod()
  -> validate model exists
  -> spawn ssh tail -f ~/.vllm_logs/<name>.log
  -> inherit stdio
  -> wait until Ctrl+C / process exit
```

### 6.3 关键语义

- 它是纯观看命令，不修改状态
- 依赖远端日志文件存在
- `FORCE_COLOR=1` 用来保留彩色输出

---

## 7. `agent` 时序

### 7.1 目标

`agent` 是把已启动模型暴露给交互式 agent CLI 的入口。

### 7.2 当前实现状态

当前 Python 版 `prompt_model()` 已经完成了：

- pod/model 解析
- OpenAI-compatible base URL 拼装
- provider registry 自动补全
- streaming 输出
- fallback 到非流式 HTTP 请求
- 多轮 REPL
- `Ctrl+C` 中断当前响应后回到提示符
- `:help / :retry / :model / :stop` 命令集

### 7.3 预期执行时序

```text
pi agent <name> [messages...]
  -> resolve pod/model
  -> build endpoint metadata
  -> health check
  -> enter REPL
  -> optional initial prompt
  -> interactive chat loop
  -> stream output or fallback HTTP
  -> accept :help / :retry / :model / :stop
  -> exit cleanly
```

### 7.4 关键语义

- `agent` 不直接跟模型通信，而是把本地 model 信息转换成 agent runtime 参数
- 交互模式和一次性消息模式共用同一套入口参数
- `:model next / :model prev` 按当前 pod 的模型名称排序后环形切换
- `:retry keep` 会保留上下文重试上一轮
- `:retry clear` 会清空上下文后重试上一轮
- `Ctrl+C` 只中断当前生成，不退出 REPL

### 7.5 REPL 命令集

```text
:help
  -> print command help

:model
  -> show current pod/model mapping

:model list
  -> list models on current pod

:model next / :model prev
  -> switch to adjacent model on current pod

:model <name>
  -> switch to explicit model on current pod

:retry
:retry keep
  -> retry last prompt and keep history

:retry clear
  -> clear history and retry last prompt

:stop
  -> exit REPL
```

### 7.6 交互示例

```text
$ pi agent qwen3
[pods] endpoint qwen3 -> qwen3:Qwen3-32B-Instruct @ 10.0.0.12:8001 (gpu-lab) status=healthy
qwen3> hello
Hello! How can I help you today?
qwen3> :model next
[pods] switched to qwen3 -> qwen3:Qwen3-14B-Instruct @ 10.0.0.12:8002 (gpu-lab) status=healthy
qwen3> explain the difference between keep and clear retry
...
qwen3> :retry keep
...           # 保留前文上下文，重新生成上一轮回答
qwen3> :retry clear
...           # 清空上下文后，仅用上一轮 prompt 重新生成
qwen3> :model prev
[pods] switched to qwen3 -> qwen3:Qwen3-32B-Instruct @ 10.0.0.12:8001 (gpu-lab) status=healthy
qwen3> :stop
[pods] chat session stopped
```

---

## 8. 关键数据模型

### 8.1 Pod

```python
@dataclass(slots=True)
class GPU:
    id: int
    name: str
    memory: str


@dataclass(slots=True)
class PodModel:
    model: str
    port: int
    gpu: list[int]
    pid: int


@dataclass(slots=True)
class Pod:
    ssh: str
    gpus: list[GPU]
    models: dict[str, PodModel]
    models_path: str | None = None
    vllm_version: str | None = None
```

### 8.2 Config

```python
@dataclass(slots=True)
class Config:
    active: str | None
    pods: dict[str, Pod]
```

---

## 9. Python 重写路径

### 推荐拆分

- `pods.config`：本地配置存储
- `pods.ssh`：SSH/SCP 适配器
- `pods.models`：模型兼容性与 GPU 选择
- `pods.commands.setup`
- `pods.commands.start`
- `pods.commands.stop`
- `pods.commands.logs`
- `pods.commands.agent`

### 推荐技术栈

- CLI：`typer` 或 `click`
- SSH：`asyncssh` 或标准库 `subprocess`
- 配置：`pydantic` / `dataclasses`
- 日志流：`asyncio` + subprocess stream

### 取舍

- 如果要最快得到可用版本，优先实现 `setup/start/stop/logs`
- `agent` 可以先只负责参数拼装，把真正的交互 runtime 放到 `pi_agent`
- 如果要保留现有体验，`logs` 需要保留颜色透传和 Ctrl+C 中断行为
