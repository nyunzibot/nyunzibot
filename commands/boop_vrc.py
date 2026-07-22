import logging
import re
import aiohttp
import discord
from discord import app_commands
from typing import Optional

from bot.safe_defer import safe_defer
from bot.vrc_client import vrc_client

log = logging.getLogger("nyunzi")

def extract_emote_id_and_anim(emote_str: str) -> Optional[tuple[str, bool]]:
    # Match standard and animated custom emotes: <a:name:id> or <:name:id>
    match = re.search(r'<(a?):[a-zA-Z0-9_]+:([0-9]+)>', emote_str)
    if match:
        is_animated = bool(match.group(1))
        emote_id = match.group(2)
        return emote_id, is_animated
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

        extracted = extract_emote_id_and_anim(emote)
        if not extracted:
            await interaction.followup.send("Could not extract a valid custom Discord emote from the input.", ephemeral=True)
            return
            
        emote_id, is_animated = extracted
        
        # Determine the order of extensions to try based on whether it claims to be animated
        if is_animated:
            extensions = ['gif', 'webp', 'png']
        else:
            extensions = ['webp', 'png', 'gif']
            
        # Download the emote
        image_bytes = None
        emote_url = None
        try:
            # Discord CDN often requires a User-Agent, otherwise it returns 403 Forbidden
            headers = {"User-Agent": "DiscordBot (https://github.com/nyunzibot/nyunzibot, 1.0)"}
            async with aiohttp.ClientSession(headers=headers) as session:
                for ext in extensions:
                    test_url = f"https://cdn.discordapp.com/emojis/{emote_id}.{ext}"
                    async with session.get(test_url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            emote_url = test_url
                            break
                        else:
                            log.debug(f"Tried {test_url}, got {resp.status}")
                
                if not image_bytes:
                    await interaction.followup.send(f"Failed to download the emote image from Discord. All formats returned an error.", ephemeral=True)
                    return
        except Exception as e:
            log.error(f"Error downloading emote: {e}")
            await interaction.followup.send(f"Error downloading emote image: {e}", ephemeral=True)
            return

        frames = 0
        frames_over_time = 0
        filename = f"emote.{'gif' if emote_url.endswith('.gif') else ('webp' if emote_url.endswith('.webp') else 'png')}"
        
        if is_animated:
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

