import discord
import re
import urllib.parse
import importlib
import logging

log = logging.getLogger("nyunzi")

class DynamicActionItem(discord.ui.DynamicItem[discord.ui.Button], template=r'act:(?P<action>[a-z]+):(?P<btn>[a-z]+):(?P<actor>[0-9]+):(?P<target>[0-9]+):(?P<taghash>[^:]*)'):
    def __init__(self, action: str, btn: str, actor_id: int, target_id: int, taghash: str, custom_id: str):
        super().__init__(discord.ui.Button(custom_id=custom_id))
        self.action_name = action
        self.btn = btn
        self.actor_id = actor_id
        self.target_id = target_id
        self.taghash = taghash

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Item, match: re.Match[str], /):
        return cls(match['action'], match['btn'], int(match['actor']), int(match['target']), match['taghash'], match.string)

    async def callback(self, interaction: discord.Interaction):
        # We need to dispatch to the correct View method.
        try:
            module = importlib.import_module(f"views.{self.action_name}_view")
            
            if self.action_name == "succ" and self.btn == "back":
                view_class_name = "SuccBackView"
            elif self.action_name == "plap" and self.btn == "back":
                view_class_name = "PlapBackView"
            else:
                view_class_name = self.action_name.capitalize() + "View"
                
            view_class = getattr(module, view_class_name)
        except Exception as e:
            log.error(f"Failed to load view for {self.action_name}: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Interaction failed. View not found.", ephemeral=True)
            else:
                await interaction.followup.send("Interaction failed. View not found.", ephemeral=True)
            return

        # Fetch users
        try:
            actor = interaction.client.get_user(self.actor_id) or await interaction.client.fetch_user(self.actor_id)
            target = interaction.client.get_user(self.target_id) or await interaction.client.fetch_user(self.target_id)
        except discord.NotFound:
            if not interaction.response.is_done():
                await interaction.response.send_message("User not found.", ephemeral=True)
            else:
                await interaction.followup.send("User not found.", ephemeral=True)
            return

        # Decode extra tags
        extra_tags = urllib.parse.unquote(self.taghash.replace('_', ':')) if self.taghash != "0" else ""

        # Instantiate view
        view = view_class(actor, target, extra_tags)
        
        # Find the correct button in the view
        button_item = None
        for child in view.children:
            if isinstance(child, discord.ui.Button):
                if (self.btn == "reroll" and child.label and "Refresh" in str(child.label)) or \
                   (self.btn == "back" and child.label and "back" in str(child.label).lower()):
                    button_item = child
                    break
                    
        if not button_item:
            if not interaction.response.is_done():
                await interaction.response.send_message("Button not found.", ephemeral=True)
            else:
                await interaction.followup.send("Button not found.", ephemeral=True)
            return

        # Call the view's callback!
        await button_item.callback(interaction)

def setup_persistent_views(bot):
    bot.add_dynamic_items(DynamicActionItem)
