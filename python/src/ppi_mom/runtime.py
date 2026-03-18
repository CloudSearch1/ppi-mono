"""Application-level skeleton for the mom runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .protocols import EventScheduler, MomHandler, SandboxConfig, SlackBot


@dataclass(slots=True)
class MomAppConfig:
    working_dir: str
    app_token: str
    bot_token: str
    sandbox: SandboxConfig


class MomApp(Protocol):
    async def run(self) -> None: ...

    async def stop(self) -> None: ...


@dataclass(slots=True)
class DefaultMomApp:
    config: MomAppConfig
    slack: SlackBot
    handler: MomHandler
    scheduler: EventScheduler | None = None

    async def run(self) -> None:
        if self.scheduler is not None:
            self.scheduler.start()
        await self.slack.start()

    async def stop(self) -> None:
        if self.scheduler is not None:
            self.scheduler.stop()


def build_mom_app(
    config: MomAppConfig,
    slack: SlackBot,
    handler: MomHandler,
    scheduler: EventScheduler | None = None,
) -> DefaultMomApp:
    return DefaultMomApp(config=config, slack=slack, handler=handler, scheduler=scheduler)
