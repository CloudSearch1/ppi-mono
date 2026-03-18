"""Workspace facade for mom.

This module is intentionally thin: it keeps the public package boundary stable
while the detailed storage/sync logic lives in the existing modules.
"""

from __future__ import annotations

from .protocols import ChannelStore, FileAttachment, LoggedMessage

__all__ = [
    "ChannelStore",
    "FileAttachment",
    "LoggedMessage",
]
