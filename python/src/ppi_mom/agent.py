"""Mom agent runner and local handler implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ppi_ai import AssistantMessage, ImageContent, TextContent, ToolResultMessage, UserMessage
from ppi_coding_agent.core.agent_session import AgentSession, AgentSessionOptions
from ppi_coding_agent.core.model_registry import InMemoryModelRegistry
from ppi_coding_agent.core.session import InMemorySessionManager
from ppi_coding_agent.core.settings import InMemorySettingsManager
from ppi_coding_agent.core.tools import LocalToolRunner, ToolDefinition, create_default_tools

from .protocols import SlackEvent
from .sandbox import SandboxConfig
from .slack import SlackBot, SlackContext
from .store import ChannelStore


@dataclass(slots=True)
class PendingMessage:
    user_name: str
    text: str
    attachments: list[dict[str, object]] = field(default_factory=list)
    timestamp: int = 0


@dataclass(slots=True)
class DefaultAgentRunner:
    """Run Slack events through the coding-agent session/model/tool loop."""

    max_history: int = 12
    _aborted: bool = field(default=False, init=False, repr=False)

    async def run(
        self,
        ctx: SlackContext,
        store: ChannelStore,
        pending_messages: list[PendingMessage] | None = None,
    ) -> dict[str, Any]:
        channel = ctx.message["channel"]
        text = str(ctx.message.get("text", "")).strip()

        if self._aborted:
            await ctx.respond("_Aborted_")
            return {"status": "aborted"}

        session = self._build_session(ctx, store)
        if pending_messages:
            session_summary = ", ".join(message.text for message in pending_messages[-3:] if message.text)
        else:
            session_summary = ""

        result = await session.run_turn(text)
        assistant_text = result.assistant_text or self._message_text(result.assistant_message)
        if session_summary and assistant_text:
            assistant_text = f"{assistant_text}\n\nRecent pending context: {session_summary}"

        await ctx.respond(assistant_text or "_No response generated_")

        if result.tool_results:
            for item in result.tool_results[:3]:
                status = "ok" if item.get("ok") else "error"
                await ctx.respond_in_thread(f"`{item.get('tool_name')}` -> {status}")

        return {
            "status": "ok",
            "session_id": result.session_id,
            "model": f"{result.model.provider}/{result.model.id}" if result.model else None,
            "fallback": result.fallback,
            "tool_results": result.tool_results,
            "history": len(session.session_manager.get_entries()),
        }

    def abort(self) -> None:
        self._aborted = True

    def _build_session(self, ctx: SlackContext, store: ChannelStore) -> AgentSession:
        channel = ctx.message["channel"]
        session_manager = InMemorySessionManager.in_memory(cwd=store._base_dir().as_posix())
        session_manager.set_session_name(channel)
        self._seed_history(session_manager, store, channel)

        model_registry = InMemoryModelRegistry()
        model = self._resolve_default_model()
        if model is not None:
            model_registry.register_provider(model.provider, [model])
            model_registry.set_default_provider(model.provider)
            model_registry.set_default_model(model.id)

        return AgentSession(
            AgentSessionOptions(
                session_manager=session_manager,
                settings_manager=InMemorySettingsManager(),
                model_registry=model_registry,
                base_tools=create_default_tools(),
                tool_runner=LocalToolRunner(cwd=store._base_dir().as_posix()),
                cwd=store._base_dir().as_posix(),
                session_name=channel,
                model=model,
            )
        )

    def _seed_history(self, session_manager: InMemorySessionManager, store: ChannelStore, channel: str) -> None:
        for entry in store.load_messages(channel)[-self.max_history :]:
            if entry.is_bot:
                session_manager.append_message(
                    AssistantMessage(
                        content=[TextContent(text=entry.text)],
                        provider="mom-local",
                        api="jsonl-history",
                    )
                )
            else:
                content: list[TextContent | ImageContent] = [TextContent(text=entry.text)]
                session_manager.append_message(UserMessage(content=content))

    def _resolve_default_model(self) -> Any | None:
        # Keep the model selection local and conservative:
        # if a real provider is registered later, AgentSession will use it.
        from ppi_ai import Model

        return Model(
            provider="openai",
            api="openai-completions",
            id="gpt-4o-mini",
            name="mom-local-fallback",
        )

    def _message_text(self, message: AssistantMessage | None) -> str:
        if message is None:
            return ""
        return "".join(block.text for block in message.content if isinstance(block, TextContent))


@dataclass(slots=True)
class MomRunner:
    sandbox: SandboxConfig | None = None


AgentRunner = DefaultAgentRunner


def build_agent_runner(sandbox: SandboxConfig | None = None) -> DefaultAgentRunner:
    _ = sandbox
    return DefaultAgentRunner()


@dataclass(slots=True)
class LocalMomHandler:
    """A small in-process handler that wires Slack events to the local runner."""

    runner: DefaultAgentRunner = field(default_factory=DefaultAgentRunner)
    running_channels: set[str] = field(default_factory=set, init=False, repr=False)

    def is_running(self, channel_id: str) -> bool:
        return channel_id in self.running_channels

    async def handle_event(self, event: SlackEvent, slack: SlackBot, is_event: bool = False) -> None:
        _ = is_event
        channel_id = event.channel
        if event.text.strip().lower() == "stop":
            await self.handle_stop(channel_id, slack)
            return
        if self.is_running(channel_id):
            await slack.post_message(channel_id, "_Already working. Say `stop` to cancel._")
            return

        self.running_channels.add(channel_id)
        try:
            channel = slack.get_channel(channel_id)
            user = slack.get_user(event.user)
            ctx = SlackContext(
                bot=slack,
                message={
                    "text": event.text,
                    "rawText": event.text,
                    "user": event.user,
                    "userName": user.user_name if user else None,
                    "channel": event.channel,
                    "ts": event.ts,
                    "attachments": event.attachments,
                },
                channel_name=channel.name if channel else "",
                store=slack.store,
                channels=slack.get_all_channels(),
                users=slack.get_all_users(),
            )

            pending: list[PendingMessage] = []
            for entry in slack.store.load_messages(channel_id)[-3:]:
                pending.append(
                    PendingMessage(
                        user_name=entry.user,
                        text=entry.text,
                        attachments=[{"original": att.original, "local": att.local} for att in entry.attachments],
                    )
                )

            await self.runner.run(ctx, slack.store, pending)
        finally:
            self.running_channels.discard(channel_id)

    async def handle_stop(self, channel_id: str, slack: SlackBot) -> None:
        if self.is_running(channel_id):
            self.runner.abort()
            self.running_channels.discard(channel_id)
            await slack.post_message(channel_id, "_Stopped_")
        else:
            await slack.post_message(channel_id, "_Nothing running_")


def build_local_mom_handler() -> LocalMomHandler:
    return LocalMomHandler()
