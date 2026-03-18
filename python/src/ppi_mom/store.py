"""Workspace persistence and JSONL storage for mom."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import httpx

from .protocols import FileAttachment as ProtocolFileAttachment
from .protocols import LoggedMessage as ProtocolLoggedMessage

LoggedMessage = ProtocolLoggedMessage
FileAttachment = ProtocolFileAttachment


@dataclass(slots=True)
class ChannelStore:
    channel_id: str = ""
    path: str = ""
    working_dir: str | None = None
    bot_token: str = ""
    _recently_logged: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def _base_dir(self) -> Path:
        base = self.working_dir or self.path or "."
        return Path(base)

    def get_channel_dir(self, channel_id: str | None = None) -> str:
        channel = channel_id or self.channel_id
        channel_dir = self._base_dir() / channel
        channel_dir.mkdir(parents=True, exist_ok=True)
        return str(channel_dir)

    def generate_local_filename(self, original_name: str, timestamp: str) -> str:
        ts = int(float(timestamp) * 1000)
        sanitized = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in original_name)
        return f"{ts}_{sanitized}"

    def process_attachments(
        self,
        channel_id: str,
        files: list[dict[str, Any]],
        timestamp: str,
    ) -> list[FileAttachment]:
        attachments: list[FileAttachment] = []
        pending_downloads: list[tuple[Path, str]] = []
        channel_dir = Path(self.get_channel_dir(channel_id))
        attachments_dir = channel_dir / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            url = file.get("url_private_download") or file.get("url_private")
            name = file.get("name")
            if not url or not name:
                continue
            local_name = self.generate_local_filename(name, timestamp)
            local_rel = f"{channel_id}/attachments/{local_name}"
            attachments.append(FileAttachment(original=name, local=local_rel))
            pending_downloads.append((self._base_dir() / local_rel, url))

        if pending_downloads:
            try:
                asyncio.get_running_loop()
                for file_path, url in pending_downloads:
                    asyncio.create_task(self._download_attachment_async(file_path, url))
            except RuntimeError:
                for file_path, url in pending_downloads:
                    self._download_attachment_sync(file_path, url)

        return attachments

    async def _download_attachment_async(self, file_path: Path, url: str) -> None:
        try:
            await asyncio.to_thread(self._download_attachment_sync, file_path, url)
        except Exception as exc:
            print(f"[mom] failed to download attachment {file_path}: {exc}")

    def _download_attachment_sync(self, file_path: Path, url: str) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {self.bot_token}"} if self.bot_token else {}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=60.0) as client:
            response = client.get(url)
            response.raise_for_status()
            file_path.write_bytes(response.content)

    async def log_message(
        self,
        channel_id: str | LoggedMessage,
        message: LoggedMessage | None = None,
    ) -> bool:
        if isinstance(channel_id, LoggedMessage):
            message = channel_id
            channel_id = self.channel_id
        if message is None:
            raise ValueError("message is required")

        dedupe_key = f"{channel_id}:{message.ts}"
        if dedupe_key in self._recently_logged:
            return False
        self._recently_logged[dedupe_key] = time.time()

        log_path = Path(self.get_channel_dir(channel_id)) / "log.jsonl"
        if not message.date:
            if "." in message.ts:
                message = LoggedMessage(
                    date=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(float(message.ts))),
                    ts=message.ts,
                    user=message.user,
                    text=message.text,
                    attachments=message.attachments,
                    is_bot=message.is_bot,
                )
            else:
                message = LoggedMessage(
                    date=time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(int(message.ts) / 1000)),
                    ts=message.ts,
                    user=message.user,
                    text=message.text,
                    attachments=message.attachments,
                    is_bot=message.is_bot,
                )

        payload = asdict(message)
        payload["attachments"] = [asdict(att) for att in message.attachments]
        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True

    async def log_bot_response(self, channel_id: str, text: str, ts: str) -> None:
        await self.log_message(
            channel_id,
            LoggedMessage(
                date="",
                ts=ts,
                user="bot",
                text=text,
                attachments=[],
                is_bot=True,
            ),
        )

    def load_messages(self, channel_id: str | None = None) -> list[LoggedMessage]:
        channel = channel_id or self.channel_id
        log_path = Path(self.get_channel_dir(channel)) / "log.jsonl"
        if not log_path.exists():
            return []

        messages: list[LoggedMessage] = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                attachments = [
                    FileAttachment(original=item["original"], local=item["local"])
                    for item in raw.get("attachments", [])
                    if isinstance(item, dict) and "original" in item and "local" in item
                ]
                messages.append(
                    LoggedMessage(
                        date=str(raw.get("date", "")),
                        ts=str(raw.get("ts", "")),
                        user=str(raw.get("user", "")),
                        text=str(raw.get("text", "")),
                        attachments=attachments,
                        is_bot=bool(raw.get("is_bot", False)),
                    )
                )
            except Exception:
                continue
        return messages

    def get_last_timestamp(self, channel_id: str | None = None) -> str | None:
        messages = self.load_messages(channel_id)
        if not messages:
            return None
        return messages[-1].ts
