import discord
from discord.ext import commands

def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    return commands.Bot(command_prefix="!", intents=intents)
