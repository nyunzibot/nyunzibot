import discord
from discord import app_commands

from bot.safe_defer import safe_defer
from db.runtime import STATS_DB

def setup(bot: discord.Client):
    @bot.tree.command(name="stats", description="View plap + succ stats (DM only)")
    @app_commands.allowed_contexts(dms=True, guilds=False, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=False)
    async def stats(interaction: discord.Interaction, user: discord.User | None = None):
        ok = await safe_defer(interaction, thinking=False)
        if not ok:
            return

        user = user or interaction.user
        pl = await STATS_DB.get_user("plap", user.id)
        su = await STATS_DB.get_user("succ", user.id)

        embed = discord.Embed(
            title="📊 Stats",
            description=(
                f"**User:** **{user.display_name}**\n\n"
                f"**👋 Plap**\n"
                f"• **Given:** {pl['given']}\n"
                f"• **Received:** {pl['received']}\n"
                f"• **Backs:** {pl['backs']}\n\n"
                f"**🫦 Succ**\n"
                f"• **Given:** {su['given']}\n"
                f"• **Received:** {su['received']}\n"
                f"• **Backs:** {su['backs']}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)
