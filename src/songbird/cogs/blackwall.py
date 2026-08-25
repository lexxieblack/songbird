from collections.abc import Callable
from typing import Any

import discord

from songbird.bot import SongbirdBot
from songbird.cogs.base import BaseCog
from songbird.models.management.exceptions import BlackwallNotFoundError
from songbird.ui.views.blackwall import BlackwallView
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class BlackwallCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

    @discord.slash_command(
        name="blackwall",
        description="Manage the blackwall channel for this server",
    )
    async def blackwall(self, ctx: discord.ApplicationContext) -> None:
        if not self.services.blackwall:
            await self.send_error(ctx, "The blackwall service is not available.")
            return

        if not ctx.guild or type(ctx.author) is not discord.Member:
            await self.send_error(ctx, "This command can only be used in a server.", ephemeral=True)
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this command.", ephemeral=True)
            return

        await ctx.defer()

        if await self._check_banned(ctx):
            return

        guild_id = ctx.guild.id
        if ctx.channel is None:
            await self.send_error(ctx, "Could not determine the current channel.")
            return
        channel_id = ctx.channel.id

        try:
            blackwall = await self.services.blackwall.get_blackwall(guild_id)
        except BlackwallNotFoundError:
            blackwall = None
        except Exception as e:
            self.logger.exception("Failed to get blackwall config", guild_id=guild_id, error=e)
            await self.send_error(ctx, "Failed to check blackwall status.")
            return

        async def on_set_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            try:
                if blackwall:
                    new_config = await self.services.blackwall.update_channel(guild_id, channel_id)  # pyright: ignore[reportOptionalMemberAccess]
                else:
                    new_config = await self.services.blackwall.create_blackwall(guild_id, channel_id)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:
                self.logger.exception("Failed to set blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to set blackwall channel.", ephemeral=True)
                return

            new_view = _make_view(
                new_config.channel_id,
                new_config.whitelisted_roles,
                new_config.banned_count,
                on_set_channel,
                on_remove_channel,
                on_edit_roles,
            )
            await interaction.edit_original_response(view=new_view)

        async def on_remove_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            try:
                updated = await self.services.blackwall.update_channel(guild_id, None)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:
                self.logger.exception("Failed to remove blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to remove blackwall channel.", ephemeral=True)
                return

            new_view = _make_view(
                None,
                updated.whitelisted_roles,
                updated.banned_count,
                on_set_channel,
                on_remove_channel,
                on_edit_roles,
            )
            await interaction.edit_original_response(view=new_view)

        async def on_edit_roles(interaction: discord.Interaction) -> None:
            pass

        p_channel_id = blackwall.channel_id if blackwall else None
        p_roles = blackwall.whitelisted_roles if blackwall else []
        p_banned_count = blackwall.banned_count if blackwall else 0

        new_view = _make_view(
            p_channel_id,
            p_roles,
            p_banned_count,
            on_set_channel,
            on_remove_channel,
            on_edit_roles,
        )
        await ctx.respond(view=new_view)


def _make_view(
    channel_id: int | None,
    whitelisted_roles: list[int],
    banned_count: int,
    on_set_channel: Callable[[discord.Interaction], Any],
    on_remove_channel: Callable[[discord.Interaction], Any],
    on_edit_roles: Callable[[discord.Interaction], Any],
) -> BlackwallView:
    return BlackwallView(
        channel_id=channel_id,
        roles=whitelisted_roles,
        banned_count=banned_count,
        on_set_channel=on_set_channel,
        on_remove_channel=on_remove_channel,
        on_edit_roles=on_edit_roles,
    )


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(BlackwallCog(bot))
