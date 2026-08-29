from collections.abc import Callable
from typing import Any

import discord

from songbird.bot import SongbirdBot
from songbird.cogs.base import BaseCog
from songbird.config import Settings
from songbird.ui.views.blackwall import BlackwallEditRolesView, BlackwallView
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class BlackwallCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

    def _missing_channel_permissions(self, guild: discord.Guild, channel_id: int, required: list[str]) -> str | None:
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return f"The configured channel <#{channel_id}> is not a text channel."

        if guild.me is None:
            return "Could not determine the bot's permissions in the selected channel."

        perms = channel.permissions_for(guild.me)
        missing = [p for p in required if not getattr(perms, p)]
        if missing:
            names = ", ".join(p.replace("_", " ").title() for p in missing)
            return f"The bot is missing required permissions in <#{channel_id}>: {names}. Grant them and try again."
        return None

    @discord.slash_command(
        name="blackwall",
        description="Manage the blackwall channel for this server",
    )
    async def blackwall(self, ctx: discord.ApplicationContext) -> None:
        if not self.services.blackwall:
            await self.send_error(ctx, "The blackwall service is not available.")
            return

        if not ctx.guild or not isinstance(ctx.author, discord.Member):
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
            if not blackwall:
                blackwall = await self.services.blackwall.create_blackwall(guild_id, channel_id)
        except Exception as e:
            self.logger.exception("Failed to get blackwall config", guild_id=guild_id, error=e)
            await self.send_error(ctx, "Failed to check blackwall status.")
            return

        async def on_set_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            if interaction.guild is None:
                await interaction.followup.send("Could not determine the guild.", ephemeral=True)
                return
            if error := self._missing_channel_permissions(
                interaction.guild, channel_id, ["view_channel", "send_messages", "ban_members"]
            ):
                await interaction.followup.send(error, ephemeral=True)
                return

            try:
                new_config = await self.services.blackwall.update_channel(guild_id, channel_id)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:
                self.logger.exception("Failed to set blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to set blackwall channel.", ephemeral=True)
                return

            new_view = _make_view(
                new_config.channel_id,
                new_config.log_channel_id,
                new_config.whitelisted_roles,
                new_config.banned_count,
                on_set_channel,
                on_remove_channel,
                on_set_log_channel,
                on_remove_log_channel,
                on_edit_roles,
                self.settings,
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
                updated.log_channel_id,
                updated.whitelisted_roles,
                updated.banned_count,
                on_set_channel,
                on_remove_channel,
                on_set_log_channel,
                on_remove_log_channel,
                on_edit_roles,
                self.settings,
            )
            await interaction.edit_original_response(view=new_view)

        async def on_set_log_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            if interaction.guild is None:
                await interaction.followup.send("Could not determine the guild.", ephemeral=True)
                return
            if error := self._missing_channel_permissions(interaction.guild, channel_id, ["view_channel", "send_messages"]):
                await interaction.followup.send(error, ephemeral=True)
                return

            try:
                new_config = await self.services.blackwall.update_log_channel(guild_id, channel_id)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:
                self.logger.exception("Failed to set blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to set blackwall channel.", ephemeral=True)
                return

            new_view = _make_view(
                new_config.channel_id,
                new_config.log_channel_id,
                new_config.whitelisted_roles,
                new_config.banned_count,
                on_set_channel,
                on_remove_channel,
                on_set_log_channel,
                on_remove_log_channel,
                on_edit_roles,
                self.settings,
            )
            await interaction.edit_original_response(view=new_view)

        async def on_remove_log_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            try:
                updated = await self.services.blackwall.update_channel(guild_id, None)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:
                self.logger.exception("Failed to remove blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to remove blackwall channel.", ephemeral=True)
                return

            new_view = _make_view(
                updated.channel_id,
                None,
                updated.whitelisted_roles,
                updated.banned_count,
                on_set_channel,
                on_remove_channel,
                on_set_log_channel,
                on_remove_log_channel,
                on_edit_roles,
                self.settings,
            )
            await interaction.edit_original_response(view=new_view)

        async def on_edit_roles(interaction: discord.Interaction) -> None:
            try:
                current = await self.services.blackwall.get_blackwall(guild_id)  # pyright: ignore[reportOptionalMemberAccess]
                current_roles = current.whitelisted_roles  # pyright: ignore[reportOptionalMemberAccess]
            except Exception:
                current_roles = blackwall.whitelisted_roles

            async def on_save_roles(interaction: discord.Interaction) -> None:
                await interaction.response.defer()
                selected = edit_view.role_select.values
                new_roles = [r.id for r in selected] if selected is not None else current_roles

                try:
                    updated = await self.services.blackwall.update_roles(guild_id, new_roles)  # pyright: ignore[reportOptionalMemberAccess]
                except Exception as e:
                    self.logger.exception("Failed to update blackwall roles", guild_id=guild_id, error=e)
                    await interaction.followup.send("Failed to update roles.", ephemeral=True)
                    return

                new_view = _make_view(
                    updated.channel_id,
                    updated.log_channel_id,
                    updated.whitelisted_roles,
                    updated.banned_count,
                    on_set_channel,
                    on_remove_channel,
                    on_set_log_channel,
                    on_remove_log_channel,
                    on_edit_roles,
                    self.settings,
                )
                await interaction.edit_original_response(view=new_view)

            async def on_cancel_edit(interaction: discord.Interaction) -> None:
                current_view = _make_view(
                    blackwall.channel_id,
                    blackwall.log_channel_id,
                    current_roles,
                    blackwall.banned_count,
                    on_set_channel,
                    on_remove_channel,
                    on_set_log_channel,
                    on_remove_log_channel,
                    on_edit_roles,
                    self.settings,
                )
                await interaction.response.edit_message(view=current_view)

            edit_view = BlackwallEditRolesView(
                current_roles=current_roles,
                on_save=on_save_roles,
                on_cancel=on_cancel_edit,
                settings=self.settings,
            )
            await interaction.response.edit_message(view=edit_view)

        new_view = _make_view(
            blackwall.channel_id,
            blackwall.log_channel_id,
            blackwall.whitelisted_roles,
            blackwall.banned_count,
            on_set_channel,
            on_remove_channel,
            on_set_log_channel,
            on_remove_log_channel,
            on_edit_roles,
            self.settings,
        )
        await ctx.respond(view=new_view)


def _make_view(
    channel_id: int | None,
    log_channel_id: int | None,
    whitelisted_roles: list[int],
    banned_count: int,
    on_set_channel: Callable[[discord.Interaction], Any],
    on_remove_channel: Callable[[discord.Interaction], Any],
    on_set_log_channel: Callable[[discord.Interaction], Any],
    on_remove_log_channel: Callable[[discord.Interaction], Any],
    on_edit_roles: Callable[[discord.Interaction], Any],
    settings: Settings,
) -> BlackwallView:
    return BlackwallView(
        channel_id=channel_id,
        log_channel_id=log_channel_id,
        roles=whitelisted_roles,
        banned_count=banned_count,
        on_set_channel=on_set_channel,
        on_remove_channel=on_remove_channel,
        on_set_log_channel=on_set_log_channel,
        on_remove_log_channel=on_remove_log_channel,
        on_edit_roles=on_edit_roles,
        settings=settings,
    )


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(BlackwallCog(bot))
