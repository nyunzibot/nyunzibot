import logging
import asyncio
import io
import discord
from discord import ui
from typing import Optional

from bot.vrc_client import vrc_client

log = logging.getLogger("nyunzi")

class BoopVrcView(discord.ui.View):
    def __init__(
        self, 
        original_actor: discord.User,
        target_friend: str,
        image_bytes: bytes,
        filename: str,
        is_animated: bool,
        target_display_name: str,
        emote_url: str
    ):
        super().__init__(timeout=300)
        self.original_actor = original_actor
        self.target_friend = target_friend
        self.raw_image_bytes = image_bytes
        self.filename = filename
        self.is_animated = is_animated
        self.target_display_name = target_display_name
        self.emote_url = emote_url
        
        self.crop_mode = True
        self.current_fps = 0 # 0 means auto from gif/webp
        self.grid_size: Optional[Tuple[int, int]] = None
        self.background_color = "transparent"
        
        self.message: discord.Message | None = None
        self.processed_bytes: bytes = image_bytes
        self.preview_bytes: bytes = b""
        self.frames = 0
        self.frames_over_time = 0
        
        self._update_buttons()

    def _update_buttons(self):
        self.clear_items()
        
        if self.is_animated:
            # Add FPS selector
            fps_options = [
                discord.SelectOption(label="Auto (from image)", value="0", default=(self.current_fps == 0)),
                discord.SelectOption(label="5 FPS", value="5", default=(self.current_fps == 5)),
                discord.SelectOption(label="10 FPS", value="10", default=(self.current_fps == 10)),
                discord.SelectOption(label="15 FPS", value="15", default=(self.current_fps == 15)),
                discord.SelectOption(label="20 FPS", value="20", default=(self.current_fps == 20)),
                discord.SelectOption(label="24 FPS", value="24", default=(self.current_fps == 24)),
                discord.SelectOption(label="30 FPS", value="30", default=(self.current_fps == 30)),
                discord.SelectOption(label="45 FPS", value="45", default=(self.current_fps == 45)),
                discord.SelectOption(label="60 FPS", value="60", default=(self.current_fps == 60)),
            ]
            fps_select = ui.Select(placeholder="Select FPS", options=fps_options, row=0)
            fps_select.callback = self.fps_callback
            self.add_item(fps_select)
            
            # Add Grid Size selector
            grid_options = [
                discord.SelectOption(label="Auto (Match frames)", value="0", default=(self.grid_size is None)),
                discord.SelectOption(label="2x2 (4 frames)", value="2", default=(self.grid_size == (2, 2))),
                discord.SelectOption(label="4x4 (16 frames)", value="4", default=(self.grid_size == (4, 4))),
                discord.SelectOption(label="8x8 (64 frames)", value="8", default=(self.grid_size == (8, 8))),
            ]
            grid_select = ui.Select(placeholder="Select Grid Size", options=grid_options, row=1)
            grid_select.callback = self.grid_size_callback
            self.add_item(grid_select)
            
            # Add Crop Toggle
            crop_btn = ui.Button(
                label="Crop: Fill" if self.crop_mode else "Crop: Fit", 
                style=discord.ButtonStyle.primary if self.crop_mode else discord.ButtonStyle.secondary,
                row=2
            )
            crop_btn.callback = self.toggle_crop_callback
            self.add_item(crop_btn)
            
        send_btn = ui.Button(label="Send Boop!", style=discord.ButtonStyle.success, row=2 if self.is_animated else 1)
        send_btn.callback = self.send_callback
        self.add_item(send_btn)
        
        cancel_btn = ui.Button(label="Cancel", style=discord.ButtonStyle.danger, row=2 if self.is_animated else 1)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.original_actor.id:
            await interaction.response.send_message("Only the person who initiated the boop can interact with this.", ephemeral=True)
            return False
        return True

    async def _process_image(self):
        """Processes the sprite sheet based on current settings"""
        from bot.sprite_generator import generate_vrc_sprite_sheet, generate_vrc_static_emoji
        
        if not self.is_animated:
            try:
                self.processed_bytes = await asyncio.to_thread(generate_vrc_static_emoji, self.raw_image_bytes)
            except Exception as e:
                log.error(f"Failed to generate static emoji: {e}")
                self.processed_bytes = self.raw_image_bytes
            self.frames = 0
            self.frames_over_time = 0
            return
        
        try:
            sprite_bytes, preview_bytes, num_frames, fps = await asyncio.to_thread(
                generate_vrc_sprite_sheet, 
                self.raw_image_bytes, 
                self.crop_mode,
                self.grid_size,
                self.background_color,
                self.current_fps
            )
            self.processed_bytes = sprite_bytes
            self.preview_bytes = preview_bytes
            self.frames = num_frames
            
            self.frames_over_time = fps
        except Exception as e:
            log.error(f"Failed to generate sprite sheet in UI: {e}")

    async def get_preview_kwargs(self) -> dict:
        """Returns the kwargs (embed, file) for editing/sending the message"""
        await self._process_image()
        
        embed = discord.Embed(
            title="Preview VRChat Emoji",
            description=f"Previewing boop for **{self.target_display_name}**.\nReview the animated preview and sprite sheet below.",
            color=discord.Color.blurple()
        )
        
        files = []
        if self.is_animated:
            embed.add_field(name="Settings", value=f"Crop Mode: {'Fill' if self.crop_mode else 'Fit'}\nFPS: {self.frames_over_time} (Total Frames: {self.frames})")
            
            sprite_file = discord.File(fp=io.BytesIO(self.processed_bytes), filename="spritesheet.png")
            preview_file = discord.File(fp=io.BytesIO(self.preview_bytes), filename="preview.gif")
            
            embed.set_image(url="attachment://preview.gif")
            embed.set_thumbnail(url="attachment://spritesheet.png")
            files = [preview_file, sprite_file]
        else:
            file_ext = "png" if self.is_animated else ("gif" if self.filename.endswith(".gif") else "webp")
            file_name = f"preview.{file_ext}"
            
            file = discord.File(fp=io.BytesIO(self.processed_bytes), filename=file_name)
            embed.set_image(url=f"attachment://{file_name}")
            files = [file]
        
        return {"embed": embed, "files": files, "view": self}

    async def fps_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        val = interaction.data.get("values", ["0"])[0]
        self.current_fps = int(val)
        
        self._update_buttons()
        kwargs = await self.get_preview_kwargs()
        files = kwargs.pop("files")
        await interaction.edit_original_response(**kwargs, attachments=files)

    async def grid_size_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        val = interaction.data.get("values", ["0"])[0]
        if val == "0":
            self.grid_size = None
        else:
            size = int(val)
            self.grid_size = (size, size)
            
        self._update_buttons()
        kwargs = await self.get_preview_kwargs()
        files = kwargs.pop("files")
        await interaction.edit_original_response(**kwargs, attachments=files)

    async def toggle_crop_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.crop_mode = not self.crop_mode
        
        self._update_buttons()
        kwargs = await self.get_preview_kwargs()
        files = kwargs.pop("files")
        await interaction.edit_original_response(**kwargs, attachments=files)

    async def send_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Disable buttons and say uploading
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)
        
        filename_to_upload = "emote.png" if self.is_animated else self.filename
        
        success, msg = await vrc_client.upload_emoji_and_boop(
            self.target_friend, 
            self.processed_bytes, 
            filename_to_upload, 
            frames=self.frames, 
            frames_over_time=self.frames_over_time
        )
        
        self.stop()
        
        if success:
            embed = discord.Embed(
                description=f"**{self.original_actor.display_name}** booped **{self.target_display_name}** in VRChat!",
                color=discord.Color.brand_green()
            )
            embed.set_thumbnail(url=self.emote_url)
            embed.set_footer(text=f"Target VRC ID: {self.target_friend}")
            await interaction.edit_original_response(embed=embed, attachments=[], view=None)
        else:
            await interaction.edit_original_response(content=f"Failed to boop in VRChat: {msg}", embed=None, attachments=[], view=None)

    async def cancel_callback(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(content="Boop cancelled.", embed=None, attachments=[], view=None)
