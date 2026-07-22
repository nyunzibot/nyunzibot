import logging
import re
import aiohttp
import discord
from discord import app_commands
from typing import Optional

from bot.safe_defer import safe_defer
from bot.vrc_client import vrc_client

log = logging.getLogger("nyunzi")

def extract_emote_url(emote_str: str) -> Optional[str]:
    # Match standard and animated custom emotes: <a:name:id> or <:name:id>
    match = re.search(r'<(a?):[a-zA-Z0-9_]+:([0-9]+)>', emote_str)
    if match:
        is_animated = bool(match.group(1))
        emote_id = match.group(2)
        ext = "gif" if is_animated else "png"
        return f"https://cdn.discordapp.com/emojis/{emote_id}.{ext}"
    return None

async def friend_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    if not vrc_client.ready:
        return []
    results = vrc_client.search_friends(current)
    return [app_commands.Choice(name=name, value=vid) for name, vid in results]

def setup(bot: discord.Client):
    @bot.tree.command(name="boop-vrc", description="Upload a Discord emote to VRChat and boop a user!")
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    @app_commands.describe(
        emote="The Discord emote to use",
        target_friend="The target VRChat friend to boop"
    )
    @app_commands.autocomplete(target_friend=friend_autocomplete)
    async def boop_vrc(
        interaction: discord.Interaction, 
        emote: str, 
        target_friend: str
    ):
        ok = await safe_defer(interaction, thinking=True)
        if not ok:
            return

        log.info(f"[CMD] /boop-vrc actor={interaction.user.id} vrc_id={target_friend}")

        if not vrc_client.ready:
            await interaction.followup.send("VRChat client is not configured or failed to authenticate. Check bot configuration.", ephemeral=True)
            return
            
        if not target_friend.startswith("usr_"):
            await interaction.followup.send("Invalid VRChat User ID. It should start with 'usr_'.", ephemeral=True)
            return

        emote_url = extract_emote_url(emote)
        if not emote_url:
            await interaction.followup.send("Could not extract a valid custom Discord emote from the input.", ephemeral=True)
            return
            
        # Download the emote
        try:
            # Discord CDN often requires a User-Agent, otherwise it returns 403 Forbidden
            headers = {"User-Agent": "DiscordBot (https://github.com/nyunzibot/nyunzibot, 1.0)"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(emote_url) as resp:
                    if resp.status != 200:
                        # Fallback to webp if png fails (Discord recently prefers webp for static)
                        if emote_url.endswith('.png'):
                            fallback_url = emote_url.replace('.png', '.webp')
                            async with session.get(fallback_url) as resp2:
                                if resp2.status != 200:
                                    await interaction.followup.send(f"Failed to download the emote image from Discord (HTTP {resp2.status} on fallback, originally {resp.status}).", ephemeral=True)
                                    return
                                image_bytes = await resp2.read()
                                emote_url = fallback_url # Update for embed thumbnail
                        else:
                            await interaction.followup.send(f"Failed to download the emote image from Discord (HTTP {resp.status}).", ephemeral=True)
                            return
                    else:
                        image_bytes = await resp.read()
        except Exception as e:
            log.error(f"Error downloading emote: {e}")
            await interaction.followup.send(f"Error downloading emote image: {e}", ephemeral=True)
            return

        frames = 0
        frames_over_time = 0
        filename = f"emote.{'gif' if emote_url.endswith('.gif') else 'png'}"
        
        if emote_url.endswith('.gif'):
            try:
                from bot.sprite_generator import generate_vrc_sprite_sheet
                import asyncio
                
                # generate_vrc_sprite_sheet is CPU bound, run in thread
                sprite_bytes, num_frames, fps = await asyncio.to_thread(generate_vrc_sprite_sheet, image_bytes)
                
                image_bytes = sprite_bytes
                frames = num_frames
                frames_over_time = fps
                filename = "emote.png" # VRChat expects PNG sprite sheet
            except Exception as e:
                log.error(f"Failed to generate sprite sheet: {e}")
                await interaction.followup.send("Failed to process animated emote into VRChat sprite sheet.", ephemeral=True)
                return

        # Upload and Boop
        success, msg = await vrc_client.upload_emoji_and_boop(
            target_friend, image_bytes, filename, 
            frames=frames, frames_over_time=frames_over_time
        )
        
        if success:
            # We don't have the VRChat display name easily accessible here (we only have the ID target_friend),
            # but we can try to find it from the autocomplete cache.
            target_display_name = next((name for name, vid in vrc_client.friends_cache if vid == target_friend), target_friend)
            embed = discord.Embed(
                description=f"**{interaction.user.display_name}** booped **{target_display_name}** in VRChat!",
                color=discord.Color.brand_green()
            )
            embed.set_thumbnail(url=emote_url)
            embed.set_footer(text=f"Target VRC ID: {target_friend}")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"Failed to boop in VRChat: {msg}", ephemeral=True)

