from collections.abc import Callable
from typing import Any, NamedTuple

import discord

from songbird.bot import SongbirdBot
from songbird.cogs.base import BaseCog
from songbird.config import Settings
from songbird.models.management.blackwall import Blackwall, BlackwallPunishment
from songbird.ui.views.blackwall.__main__ import BlackwallView
from songbird.ui.views.blackwall.edit_punishment import BlackwallEditPunishmentView
from songbird.ui.views.blackwall.edit_roles import BlackwallEditRolesView
from songbird.utils.logging import get_logger

logger = get_logger(__name__)


class _Callbacks(NamedTuple):
    on_set_channel: Callable[[discord.Interaction], Any]
    on_remove_channel: Callable[[discord.Interaction], Any]
    on_set_log_channel: Callable[[discord.Interaction], Any]
    on_remove_log_channel: Callable[[discord.Interaction], Any]
    on_edit_roles: Callable[[discord.Interaction], Any]
    on_edit_punishment: Callable[[discord.Interaction], Any]


class BlackwallCog(BaseCog):
    def __init__(self, bot: "SongbirdBot") -> None:
        super().__init__(bot)

    def _missing_channel_permissions(self, guild: discord.Guild, channel_id: int, required: list[str]) -> str | None:
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return f"The configured channel <#{channel_id}> is not a text channel."

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
        blackwall_service = self.services.blackwall
        if blackwall_service is None:
            await self.send_error(ctx, "The blackwall service is not available.")
            return

        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            await self.send_error(ctx, "This command can only be used in a server.", ephemeral=True)
            return

        if not ctx.author.guild_permissions.administrator:
            await ctx.respond("You do not have permission to use this command.", ephemeral=True)
            return

        await ctx.defer()

        guild_id = ctx.guild.id
        if ctx.channel is None:
            await self.send_error(ctx, "Could not determine the current channel.")
            return
        channel_id = ctx.channel.id

        try:
            blackwall = await blackwall_service.get_blackwall(guild_id)
            if not blackwall:
                blackwall = await blackwall_service.create_blackwall(guild_id)
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
                new_config = await blackwall_service.update_channel(guild_id, channel_id)
            except Exception as e:
                self.logger.exception("Failed to set blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to set blackwall channel.", ephemeral=True)
                return

            await interaction.edit_original_response(view=_make_view(new_config, callbacks, self.settings))

        async def on_remove_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            try:
                updated = await blackwall_service.update_channel(guild_id, None)
            except Exception as e:
                self.logger.exception("Failed to remove blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to remove blackwall channel.", ephemeral=True)
                return

            await interaction.edit_original_response(view=_make_view(updated, callbacks, self.settings))

        async def on_set_log_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            if interaction.guild is None:
                await interaction.followup.send("Could not determine the guild.", ephemeral=True)
                return
            if error := self._missing_channel_permissions(interaction.guild, channel_id, ["view_channel", "send_messages"]):
                await interaction.followup.send(error, ephemeral=True)
                return

            try:
                new_config = await blackwall_service.update_log_channel(guild_id, channel_id)
            except Exception as e:
                self.logger.exception("Failed to set blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to set blackwall channel.", ephemeral=True)
                return

            await interaction.edit_original_response(view=_make_view(new_config, callbacks, self.settings))

        async def on_remove_log_channel(interaction: discord.Interaction) -> None:
            await interaction.response.defer()

            try:
                updated = await blackwall_service.update_log_channel(guild_id, None)
            except Exception as e:
                self.logger.exception("Failed to remove blackwall channel", guild_id=guild_id, error=e)
                await interaction.followup.send("Failed to remove blackwall channel.", ephemeral=True)
                return

            await interaction.edit_original_response(view=_make_view(updated, callbacks, self.settings))

        async def on_edit_roles(interaction: discord.Interaction) -> None:
            try:
                current_blackwall = await blackwall_service.get_blackwall(guild_id)
                current_roles = (
                    current_blackwall.whitelisted_roles if current_blackwall is not None else blackwall.whitelisted_roles
                )
            except Exception:
                current_roles = blackwall.whitelisted_roles

            async def on_save_roles(interaction: discord.Interaction) -> None:
                await interaction.response.defer()
                selected = edit_view.role_select.values
                new_roles = [r.id for r in selected] if selected is not None else current_roles

                try:
                    updated = await blackwall_service.update_roles(guild_id, new_roles)
                except Exception as e:
                    self.logger.exception("Failed to update blackwall roles", guild_id=guild_id, error=e)
                    await interaction.followup.send("Failed to update roles.", ephemeral=True)
                    return

                await interaction.edit_original_response(view=_make_view(updated, callbacks, self.settings))

            async def on_cancel_edit(interaction: discord.Interaction) -> None:
                current = await blackwall_service.get_blackwall(guild_id) or blackwall
                await interaction.response.edit_message(view=_make_view(current, callbacks, self.settings))

            edit_view = BlackwallEditRolesView(
                current_roles=current_roles,
                on_save=on_save_roles,
                on_cancel=on_cancel_edit,
                settings=self.settings,
            )
            await interaction.response.edit_message(view=edit_view)

        async def on_edit_punishment(interaction: discord.Interaction) -> None:
            latest = await blackwall_service.get_blackwall(guild_id)
            current_punishment = latest.punishment if latest else blackwall.punishment

            async def on_save_punishment(interaction: discord.Interaction) -> None:
                await interaction.response.defer()
                selected = edit_view.punishment_select.values
                new_punishment = BlackwallPunishment(selected[0]) if selected else current_punishment

                try:
                    updated = await blackwall_service.update_punishment(guild_id, new_punishment)
                except Exception as e:
                    self.logger.exception("Failed to update blackwall punishment", guild_id=guild_id, error=e)
                    await interaction.followup.send("Failed to update punishment.", ephemeral=True)
                    return

                await interaction.edit_original_response(view=_make_view(updated, callbacks, self.settings))

            async def on_cancel_edit(interaction: discord.Interaction) -> None:
                current = await blackwall_service.get_blackwall(guild_id) or blackwall
                await interaction.response.edit_message(view=_make_view(current, callbacks, self.settings))

            edit_view = BlackwallEditPunishmentView(
                current_punishment=current_punishment,
                on_save=on_save_punishment,
                on_cancel=on_cancel_edit,
                settings=self.settings,
            )
            await interaction.response.edit_message(view=edit_view)

        callbacks = _Callbacks(
            on_set_channel=on_set_channel,
            on_remove_channel=on_remove_channel,
            on_set_log_channel=on_set_log_channel,
            on_remove_log_channel=on_remove_log_channel,
            on_edit_roles=on_edit_roles,
            on_edit_punishment=on_edit_punishment,
        )
        await ctx.respond(view=_make_view(blackwall, callbacks, self.settings))


def _make_view(config: Blackwall, callbacks: _Callbacks, settings: Settings) -> BlackwallView:
    return BlackwallView(
        channel_id=config.channel_id,
        log_channel_id=config.log_channel_id,
        roles=config.whitelisted_roles,
        banned_count=config.banned_count,
        punishment=config.punishment,
        on_set_channel=callbacks.on_set_channel,
        on_remove_channel=callbacks.on_remove_channel,
        on_set_log_channel=callbacks.on_set_log_channel,
        on_remove_log_channel=callbacks.on_remove_log_channel,
        on_edit_roles=callbacks.on_edit_roles,
        on_edit_punishment=callbacks.on_edit_punishment,
        settings=settings,
    )


def setup(bot: "SongbirdBot") -> None:
    bot.add_cog(BlackwallCog(bot))
