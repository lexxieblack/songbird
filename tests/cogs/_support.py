"""Helpers for exercising py-cord slash commands without a gateway."""

from typing import Any

import discord


async def invoke(cog: object, name: str, ctx: discord.ApplicationContext, **kwargs: Any) -> None:
    """Call a command's underlying callback with its owning cog."""
    command = getattr(cog, name)
    await command.callback(cog, ctx, **kwargs)
