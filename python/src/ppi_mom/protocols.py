"""Protocol and shared dataclass definitions for the mom runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(slots=True)
class FileAttachment:
    original: str
    local: str


@dataclass(slots=True)
class LoggedMessage:
    date: str
    ts: str
    user: str
    text: str
    attachments: list[FileAttachment] = field(default_factory=list)
    is_bot: bool = False


@dataclass(slots=True)
class SlackUser:
    id: str
    user_name: str
    display_name: str | None = None


@dataclass(slots=True)
class SlackChannel:
    id: str
    name: str


@dataclass(slots=True)
class SlackEvent:
    type: Literal["mention", "dm"]
    channel: str
    ts: str
    user: str
    text: str
    files: list[dict[str, Any]] = field(default_factory=list)
    attachments: list[FileAttachment] = field(default_factory=list)
    thread_ts: str | None = None


@dataclass(slots=True)
class ImmediateEvent:
    type: Literal["immediate"] = "immediate"
    channel_id: str = ""
    text: str = ""


@dataclass(slots=True)
class OneShotEvent:
    type: Literal["one-shot"] = "one-shot"
    channel_id: str = ""
    text: str = ""
    at: str = ""


@dataclass(slots=True)
class PeriodicEvent:
    type: Literal["periodic"] = "periodic"
    channel_id: str = ""
    text: str = ""
    schedule: str = ""
    timezone: str = ""


MomEvent = ImmediateEvent | OneShotEvent | PeriodicEvent


@dataclass(slots=True)
class SandboxConfig:
    type: Literal["host", "docker"]
    container: str | None = None


@dataclass(slots=True)
class ExecResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""


@runtime_checkable
class ChannelStore(Protocol):
    def get_channel_dir(self, channel_id: str) -> str: ...

    def process_attachments(
        self,
        channel_id: str,
        files: list[dict[str, Any]],
        timestamp: str,
    ) -> list[FileAttachment]: ...

    async def log_message(self, channel_id: str, message: LoggedMessage) -> bool: ...

    async def log_bot_response(self, channel_id: str, text: str, ts: str) -> None: ...

    def get_last_timestamp(self, channel_id: str) -> str | None: ...


@runtime_checkable
class ContextSync(Protocol):
    def sync_log_to_session_manager(self, channel_dir: str, exclude_slack_ts: str | None = None) -> int: ...


@runtime_checkable
class SandboxExecutor(Protocol):
    async def validate(self) -> None: ...

    async def exec(self, command: str, *, cwd: str | None = None) -> ExecResult: ...

    async def exec_stream(self, command: str, *, cwd: str | None = None) -> int: ...

    def get_workspace_path(self, host_path: str) -> str: ...


@runtime_checkable
class SlackContext(Protocol):
    message: Any
    channel_name: str | None
    store: ChannelStore
    channels: list[SlackChannel]
    users: list[SlackUser]

    async def respond(self, text: str, should_log: bool = True) -> None: ...

    async def replace_message(self, text: str) -> None: ...

    async def respond_in_thread(self, text: str) -> None: ...

    async def set_typing(self, is_typing: bool) -> None: ...

    async def upload_file(self, file_path: str, title: str | None = None) -> None: ...

    async def set_working(self, working: bool) -> None: ...

    async def delete_message(self) -> None: ...


@runtime_checkable
class AgentRunner(Protocol):
    async def run(
        self,
        ctx: SlackContext,
        store: ChannelStore,
        pending_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...

    def abort(self) -> None: ...


@runtime_checkable
class EventScheduler(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def register_file(self, filename: str) -> None: ...

    def cancel(self, filename: str) -> None: ...


@runtime_checkable
class MomHandler(Protocol):
    def is_running(self, channel_id: str) -> bool: ...

    async def handle_event(self, event: SlackEvent, slack: "SlackBot", is_event: bool = False) -> None: ...

    async def handle_stop(self, channel_id: str, slack: "SlackBot") -> None: ...


@runtime_checkable
class SlackBot(Protocol):
    async def start(self) -> None: ...

    def get_user(self, user_id: str) -> SlackUser | None: ...

    def get_channel(self, channel_id: str) -> SlackChannel | None: ...

    def get_all_users(self) -> list[SlackUser]: ...

    def get_all_channels(self) -> list[SlackChannel]: ...

    async def post_message(self, channel: str, text: str) -> str: ...

    async def update_message(self, channel: str, ts: str, text: str) -> None: ...

    async def delete_message(self, channel: str, ts: str) -> None: ...

    async def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str: ...

    async def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None: ...

    def log_to_file(self, channel: str, entry: object) -> None: ...

    def log_bot_response(self, channel: str, text: str, ts: str) -> None: ...

    def enqueue_event(self, event: SlackEvent) -> bool: ...
