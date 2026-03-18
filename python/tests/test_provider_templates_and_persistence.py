from __future__ import annotations

import json

from ppi_ai import (
    AssistantMessage,
    Context,
    Model,
    StreamOptions,
    TextContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from ppi_ai.providers import (
    AzureOpenAIResponsesOptions,
    AzureOpenAIResponsesProvider,
    BedrockProvider,
    MistralProvider,
    StreamChunk,
    StreamParseState,
)
from ppi_coding_agent.core.model_registry import FileModelRegistry
from ppi_coding_agent.core.schemas import available_schemas, load_schema, load_schema_registry, validate_schema
from ppi_coding_agent.core.session import InMemorySessionManager
from ppi_coding_agent.core.settings import FileSettingsManager, Settings
from ppi_coding_agent.modes.environment import build_mode_environment
from ppi_coding_agent.modes.tui import InteractiveTuiApp
from ppi_coding_agent.modes.rpc_mode import RpcMode
from ppi_coding_agent.modes.shared import parse_invocation
from ppi_tui import Key, normalize_key


def test_azure_openai_responses_build_request_uses_azure_endpoint_and_key() -> None:
    provider = AzureOpenAIResponsesProvider()
    model = Model(provider="azure-openai-responses", api="azure-openai-responses", id="gpt-5")
    context = Context(system_prompt="sys")
    options = AzureOpenAIResponsesOptions(
        api_key="secret",
        azure_base_url="https://demo.openai.azure.com/openai/v1",
        azure_deployment_name="demo-deployment",
        azure_api_version="2024-10-21",
    )

    request = provider.build_request(model, context, options)

    assert request.url == "https://demo.openai.azure.com/openai/v1/deployments/demo-deployment/responses?api-version=2024-10-21"
    assert request.headers["api-key"] == "secret"
    assert "authorization" not in request.headers
    assert request.json["model"] == "gpt-5"


def test_mistral_build_request_uses_chat_completions_path() -> None:
    provider = MistralProvider()
    model = Model(provider="mistral", api="mistral-conversations", id="mistral-small", base_url="https://api.mistral.ai/v1")
    context = Context(messages=[UserMessage(content="hello")])

    request = provider.build_request(model, context, StreamOptions(api_key="secret"))

    assert request.url == "https://api.mistral.ai/v1/chat/completions"
    assert request.json["model"] == "mistral-small"
    assert request.json["messages"][0]["role"] == "user"


def test_bedrock_request_and_chunk_parsing() -> None:
    provider = BedrockProvider()
    model = Model(provider="bedrock", api="bedrock-converse-stream", id="anthropic.claude-3-sonnet-20240229-v1:0")
    context = Context(
        system_prompt="system",
        messages=[
            UserMessage(content="hello"),
            AssistantMessage(content=[TextContent(text="world"), ToolCall(id="call_1", name="search", arguments={"q": "docs"})]),
            ToolResultMessage(tool_call_id="call_1", tool_name="search", content=[TextContent(text="result")]),
        ],
        tools=[Tool(name="search", description="search docs", parameters={"type": "object"})],
    )

    request = provider.build_request(model, context, StreamOptions(max_tokens=128, temperature=0.2))

    assert request.url.endswith("/converse-stream")
    assert request.json["modelId"] == model.id
    assert request.json["toolConfig"]["tools"][0]["toolSpec"]["name"] == "search"

    state = StreamParseState()
    provider.parse_chunk(StreamChunk(event="message_start", data={"messageId": "msg-1"}), state)
    provider.parse_chunk(StreamChunk(event="content_block_start", data={"index": 0, "content_block": {"type": "text"}}), state)
    provider.parse_chunk(StreamChunk(event="content_block_delta", data={"index": 0, "delta": {"text": "hello"}}), state)
    provider.parse_chunk(StreamChunk(event="content_block_stop", data={"index": 0}), state)
    provider.parse_chunk(StreamChunk(event="message_stop", data={"stopReason": "stop", "usage": {"inputTokens": 1, "outputTokens": 1}}), state)

    assert state.assistant_message.response_id == "msg-1"
    assert any(isinstance(block, TextContent) and block.text == "hello" for block in state.assistant_message.content)
    assert state.assistant_message.usage.input == 1


def test_session_jsonl_roundtrip(tmp_path) -> None:
    manager = InMemorySessionManager.create(cwd=".", session_dir=str(tmp_path))
    manager.append_message(UserMessage(content="hello"))
    manager.append_message(AssistantMessage(content=[TextContent(text="world")]))

    assert manager.path is not None
    assert manager.path.exists()

    header = json.loads(manager.path.read_text(encoding="utf-8").splitlines()[0])
    assert header["type"] == "session"
    assert header["version"] == 1

    reloaded = InMemorySessionManager.open(str(manager.path))
    assert len(reloaded.get_entries()) == len(manager.get_entries())
    assert isinstance(reloaded.get_entries()[0].message, UserMessage)


def test_settings_and_model_registry_roundtrip(tmp_path) -> None:
    settings = FileSettingsManager(
        global_path=tmp_path / "settings.global.json",
        project_path=tmp_path / "settings.project.json",
    )
    settings.set_global_settings(Settings(model={"default": "gpt-5"}, markdown={"block_images": False}))
    settings.set_project_settings(Settings(model={"provider": "openai"}, markdown={"block_images": True}))
    settings.save()

    reloaded_settings = FileSettingsManager(
        global_path=tmp_path / "settings.global.json",
        project_path=tmp_path / "settings.project.json",
    )
    assert reloaded_settings.get_default_model() == "gpt-5"
    assert reloaded_settings.get_default_provider() == "openai"
    assert reloaded_settings.get_block_images() is True

    registry = FileModelRegistry(path=tmp_path / "model-registry.json")
    registry.set_default_provider("openai")
    registry.set_default_model("gpt-5")
    registry.register_provider(
        "openai",
        Model(provider="openai", api="openai-responses", id="gpt-5", name="GPT-5", base_url="https://api.openai.com/v1"),
    )
    registry.save()

    reloaded_registry = FileModelRegistry(path=tmp_path / "model-registry.json")
    assert reloaded_registry.resolve_default() is not None
    assert reloaded_registry.resolve_default().id == "gpt-5"


def test_schema_files_are_loadable() -> None:
    schemas = set(available_schemas())
    assert "session-header" in schemas
    assert "session-entry" in schemas
    assert "settings" in schemas
    assert "model-registry" in schemas
    assert load_schema("settings")["title"] == "Settings"
    assert load_schema_registry()["version"] == 1
    validate_schema("settings", {"version": 1, "model": {}, "thinking": {}, "transport": {}, "compaction": {}, "retry": {}, "terminal": {}, "markdown": {}, "resources": {}, "extensions": {}, "skills": {}, "prompts": {}, "themes": {}, "packages": {}})


def test_mode_invocation_accepts_runtime_paths() -> None:
    invocation = parse_invocation(
        [
            "--mode",
            "interactive",
            "--cwd",
            "C:/work/project",
            "--config-dir",
            "C:/work/project/.ppi",
            "--session-dir",
            "C:/work/project/.ppi/sessions",
            "--session-id",
            "session_123",
            "--theme",
            "dark",
        ]
    )

    assert invocation.cwd == "C:/work/project"
    assert invocation.config_dir == "C:/work/project/.ppi"
    assert invocation.session_dir == "C:/work/project/.ppi/sessions"
    assert invocation.session_id == "session_123"
    assert invocation.theme == "dark"


def test_mode_environment_snapshot(tmp_path) -> None:
    env = build_mode_environment(
        parse_invocation(
            [
                "--mode",
                "print",
                "--cwd",
                str(tmp_path),
                "--config-dir",
                str(tmp_path / ".ppi"),
                "--session-dir",
                str(tmp_path / ".ppi" / "sessions"),
            ]
        )
    )

    snapshot = env.snapshot()
    assert snapshot["paths"]["cwd"] == str(tmp_path.resolve())
    assert "settings" in snapshot["schemas"]["names"]
    assert "session-header" in snapshot["schemas"]["names"]


def test_rpc_command_handling(tmp_path) -> None:
    env = build_mode_environment(
        parse_invocation(
            [
                "--mode",
                "rpc",
                "--cwd",
                str(tmp_path),
                "--config-dir",
                str(tmp_path / ".ppi"),
                "--session-dir",
                str(tmp_path / ".ppi" / "sessions"),
            ]
        )
    )
    rpc = RpcMode()

    response = rpc._handle_command(env, {"type": "list_schemas"})
    assert response["type"] == "response"
    assert "settings" in response["data"]

    response = rpc._handle_command(env, {"type": "describe"})
    assert response["type"] == "response"
    assert response["data"]["paths"]["cwd"] == str(tmp_path.resolve())


def test_interactive_tui_app_renders_and_handles_commands(tmp_path) -> None:
    env = build_mode_environment(
        parse_invocation(
            [
                "--mode",
                "interactive",
                "--cwd",
                str(tmp_path),
                "--config-dir",
                str(tmp_path / ".ppi"),
                "--session-dir",
                str(tmp_path / ".ppi" / "sessions"),
            ]
        )
    )
    app = InteractiveTuiApp(env)

    rendered = app.render()
    assert "pimono interactive workspace" in rendered
    assert "commands:" in rendered or "help" in rendered

    result = app.handle_line("hello world")
    assert result.action == "message"
    assert len(env.sessions.get_entries()) == 1

    app.handle_key("h")
    app.handle_key("i")
    app.handle_key(Key.backspace)
    app.handle_key("!")
    app.handle_key(Key.enter)
    assert len(env.sessions.get_entries()) == 2
    assert normalize_key("\x1b[A") == Key.up
    assert normalize_key("\x1b[200~") == Key.paste_start
    assert normalize_key("\x03") == Key.ctrl("c")

    app.handle_key("pasted chunk")
    app.handle_key(Key.enter)
    assert len(env.sessions.get_entries()) == 3

    result = app.handle_key(Key.tab)
    assert result.action == "tab"
    assert app.state.overlays[-1].title == "Completion"
