"""Discord bot entry point (runs 24/7 on the VPS — no GPU here)."""
import discord
from discord import app_commands
from discord.ext import commands

import config
from panel import PanelView, panel_embed

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    bot.add_view(PanelView())  # re-register persistent buttons after restart
    await bot.tree.sync()


@bot.event
async def on_ready():
    print(f"✅ Bot running as {bot.user} (ID: {bot.user.id})")


@bot.tree.command(name="panel", description="نشر لوحة الـUpscale (أزرار) في هذه القناة")
@app_commands.default_permissions(manage_messages=True)
async def panel(interaction: discord.Interaction):
    await interaction.channel.send(embed=panel_embed(), view=PanelView())
    await interaction.response.send_message("✅ تم نشر اللوحة.", ephemeral=True)


if __name__ == "__main__":
    bot.run(config.DISCORD_TOKEN)
