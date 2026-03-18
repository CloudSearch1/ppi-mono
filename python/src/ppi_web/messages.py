"""Web-layer message models and transformers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ppi_ai import ImageContent, Message, TextContent


@dataclass(slots=True)
class Attachment:
    id: str
    type: str
    file_name: str
    mime_type: str
    size: int
    content: str
    extracted_text: str | None = None
    preview: str | None = None


@dataclass(slots=True)
class UserMessageWithAttachments:
    role: str = "user-with-attachments"
    content: str | list[TextContent | ImageContent] = ""
    timestamp: int = 0
    attachments: list[Attachment] = field(default_factory=list)


@dataclass(slots=True)
class ArtifactMessage:
    role: str = "artifact"
    action: str = "create"
    filename: str = ""
    content: str | None = None
    title: str | None = None
    timestamp: str = ""


class MessageTransformer(Protocol):
    def __call__(self, messages: list[Any]) -> list[Message]:
        ...


def convert_attachments(attachments: list[Attachment]) -> list[TextContent | ImageContent]:
    raise NotImplementedError


def default_convert_to_llm(messages: list[Any]) -> list[Message]:
    raise NotImplementedError
