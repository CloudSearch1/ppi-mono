"""Slack adapter implementation for mom.

This module provides a lightweight local runtime that records workspace state
as JSONL while keeping the transport layer replaceable.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .protocols import SlackChannel, SlackEvent, SlackUser
from .store import ChannelStore, FileAttachment, LoggedMessage


@runtime_checkable
class SlackTransport(Protocol):
    def post_message(self, channel: str, text: str) -> str: ...

    def update_message(self, channel: str, ts: str, text: str) -> None: ...

    def delete_message(self, channel: str, ts: str) -> None: ...

    def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str: ...

    def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None: ...


@dataclass(slots=True)
class ConsoleSlackTransport:
    """A local transport that writes actions to stdout.

    This is useful as a default transport during development and tests.
    """

    prefix: str = "[slack]"

    def post_message(self, channel: str, text: str) -> str:
        ts = f"{time.time():.6f}"
        print(f"{self.prefix} post_message channel={channel} ts={ts} text={text}")
        return ts

    def update_message(self, channel: str, ts: str, text: str) -> None:
        print(f"{self.prefix} update_message channel={channel} ts={ts} text={text}")

    def delete_message(self, channel: str, ts: str) -> None:
        print(f"{self.prefix} delete_message channel={channel} ts={ts}")

    def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str:
        ts = f"{time.time():.6f}"
        print(
            f"{self.prefix} post_in_thread channel={channel} thread_ts={thread_ts} ts={ts} text={text}"
        )
        return ts

    def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None:
        print(f"{self.prefix} upload_file channel={channel} path={file_path} title={title}")


@dataclass(slots=True)
class SlackContext:
    bot: "SlackBot"
    message: dict[str, Any]
    channel_name: str = ""
    store: ChannelStore | None = None
    channels: list[SlackChannel] = field(default_factory=list)
    users: list[SlackUser] = field(default_factory=list)
    _message_ts: str | None = field(default=None, init=False, repr=False)

    async def respond(self, text: str, should_log: bool = True) -> None:
        if should_log:
            ts = await self.bot.post_message(self.message["channel"], text)
        else:
            ts = self.bot.transport.post_message(self.message["channel"], text)
        self._message_ts = ts

    async def replace_message(self, text: str) -> None:
        if self._message_ts is None:
            await self.respond(text)
            return
        await self.bot.update_message(self.message["channel"], self._message_ts, text)

    async def respond_in_thread(self, text: str) -> None:
        thread_ts = self._message_ts or self.message["ts"]
        self._message_ts = await self.bot.post_in_thread(self.message["channel"], thread_ts, text)

    async def upload_file(self, path: str, title: str | None = None) -> None:
        await self.bot.upload_file(self.message["channel"], path, title)

    async def set_typing(self, is_typing: bool) -> None:
        _ = is_typing

    async def set_working(self, working: bool) -> None:
        _ = working

    async def delete_message(self) -> None:
        if self._message_ts is not None:
            await self.bot.delete_message(self.message["channel"], self._message_ts)


class SlackBot:
    def __init__(
        self,
        token: str = "",
        *,
        workspace_dir: str = ".",
        store: ChannelStore | None = None,
        transport: SlackTransport | None = None,
        handler: Any | None = None,
    ) -> None:
        self.token = token
        self.workspace_dir = workspace_dir
        self.store = store or ChannelStore(working_dir=workspace_dir, bot_token=token)
        self.transport = transport or ConsoleSlackTransport()
        self.handler = handler
        self.users: dict[str, SlackUser] = {}
        self.channels: dict[str, SlackChannel] = {}
        self._queues: dict[str, deque[SlackEvent]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)

    def register_user(self, user: SlackUser) -> None:
        self.users[user.id] = user

    def register_channel(self, channel: SlackChannel) -> None:
        self.channels[channel.id] = channel

    def get_user(self, user_id: str) -> SlackUser | None:
        return self.users.get(user_id)

    def get_channel(self, channel_id: str) -> SlackChannel | None:
        return self.channels.get(channel_id)

    def get_all_users(self) -> list[SlackUser]:
        return list(self.users.values())

    def get_all_channels(self) -> list[SlackChannel]:
        return list(self.channels.values())

    async def post_message(self, channel: str, text: str) -> str:
        ts = self.transport.post_message(channel, text)
        await self.store.log_bot_response(channel, text, ts)
        return ts

    async def update_message(self, channel: str, ts: str, text: str) -> None:
        self.transport.update_message(channel, ts, text)

    async def delete_message(self, channel: str, ts: str) -> None:
        self.transport.delete_message(channel, ts)

    async def post_in_thread(self, channel: str, thread_ts: str, text: str) -> str:
        ts = self.transport.post_in_thread(channel, thread_ts, text)
        await self.store.log_bot_response(channel, text, ts)
        return ts

    async def upload_file(self, channel: str, file_path: str, title: str | None = None) -> None:
        self.transport.upload_file(channel, file_path, title)

    def log_to_file(self, channel: str, entry: object) -> None:
        if isinstance(entry, LoggedMessage):
            coro = self.store.log_message(channel, entry)
        elif isinstance(entry, dict):
            attachments = []
            for item in entry.get("attachments", []):
                if isinstance(item, dict) and "original" in item and "local" in item:
                    attachments.append(FileAttachment(original=item["original"], local=item["local"]))
            coro = self.store.log_message(
                channel,
                LoggedMessage(
                    date=str(entry.get("date", "")),
                    ts=str(entry.get("ts", f"{time.time():.6f}")),
                    user=str(entry.get("user", "")),
                    text=str(entry.get("text", "")),
                    attachments=attachments,
                    is_bot=bool(entry.get("is_bot", False)),
                ),
            )
        else:
            coro = self.store.log_message(
                channel,
                LoggedMessage(
                    date="",
                    ts=f"{time.time():.6f}",
                    user="unknown",
                    text=str(entry),
                    attachments=[],
                    is_bot=False,
                ),
            )

        self._run_coro(coro)

    def log_bot_response(self, channel: str, text: str, ts: str) -> None:
        self._run_coro(self.store.log_bot_response(channel, text, ts))

    def enqueue_event(self, event: SlackEvent) -> bool:
        if event.files and not event.attachments:
            event.attachments = self.store.process_attachments(event.channel, event.files, event.ts)

        self.log_to_file(
            event.channel,
            LoggedMessage(
                date="",
                ts=event.ts,
                user=event.user,
                text=event.text,
                attachments=[
                    FileAttachment(original=attachment.original, local=attachment.local)
                    for attachment in event.attachments
                ],
                is_bot=False,
            ),
        )

        if self.handler is None:
            return True

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._handle_event(event))
            return True

        queue = self._queues.setdefault(event.channel, deque())
        queue.append(event)
        worker = self._workers.get(event.channel)
        if worker is None or worker.done():
            self._workers[event.channel] = loop.create_task(self._drain_queue(event.channel))
        return True

    async def _drain_queue(self, channel: str) -> None:
        queue = self._queues.setdefault(channel, deque())
        while queue:
            event = queue.popleft()
            await self._handle_event(event)

    async def _handle_event(self, event: SlackEvent) -> None:
        if self.handler is None:
            return
        await self.handler.handle_event(event, self, True)

    def _run_coro(self, coro: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return

        loop.create_task(coro)
