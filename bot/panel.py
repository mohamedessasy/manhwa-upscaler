"""Button panel + modal — the main UI. Persistent across bot restarts."""
import asyncio

import discord

import config
import jobs


class UpscaleModal(discord.ui.Modal, title="Upscale — Manhwa"):
    source = discord.ui.TextInput(
        label="Source links (images / ZIP)",
        style=discord.TextStyle.paragraph,
        placeholder="ZIP link or direct image links (one per line, or comma-separated)",
        required=True,
        max_length=4000,
    )
    work_name = discord.ui.TextInput(
        label="Work name",
        placeholder="e.g. solo-leveling",
        required=True,
        max_length=100,
    )
    chapter = discord.ui.TextInput(
        label="Chapter number",
        placeholder="e.g. 12",
        required=True,
        max_length=20,
    )
    quality = discord.ui.TextInput(
        label=f"JPEG quality (optional, default {config.JPEG_QUALITY})",
        placeholder=str(config.JPEG_QUALITY),
        required=False,
        max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            q = int(str(self.quality.value).strip() or config.JPEG_QUALITY)
        except ValueError:
            q = config.JPEG_QUALITY
        q = max(1, min(100, q))

        embed = discord.Embed(
            title="🕐 Starting job...",
            description=f"**{self.work_name.value} / {self.chapter.value}**",
            color=0x95A5A6,
        )
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        asyncio.create_task(jobs.run_job(
            message=message,
            source=str(self.source.value),
            work_name=str(self.work_name.value).strip(),
            chapter=str(self.chapter.value).strip(),
            quality=q,
        ))


class PanelView(discord.ui.View):
    """Persistent view (timeout=None + custom_id) — buttons survive restarts."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⚡ Upscale", style=discord.ButtonStyle.primary,
                       custom_id="upscale_panel:start")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UpscaleModal())

    @discord.ui.button(label="❓ Help", style=discord.ButtonStyle.secondary,
                       custom_id="upscale_panel:help")
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=help_embed(), ephemeral=True)


def panel_embed() -> discord.Embed:
    return discord.Embed(
        title="🖼️ Manhwa Upscaler",
        description=(
            "Press **⚡ Upscale**, then enter your links, work name and chapter.\n\n"
            "**Supported sources:**\n"
            "• ZIP / CBZ link\n"
            "• Direct image links (one per line)\n\n"
            f"**Output:** {config.OUT_WIDTH}px wide · JPEG · same page count and order"
        ),
        color=0x5865F2,
    )


def help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="❓ How to use the Upscaler",
        color=0x5865F2,
        description=(
            "AI-upscales manhwa/webtoon pages on a cloud GPU, then resizes them "
            f"to **{config.OUT_WIDTH}px** width as JPEG. Page count and order never change."
        ),
    )
    embed.add_field(
        name="1 — Start",
        value="Press the **⚡ Upscale** button on the panel (or use `/panel` to post a panel).",
        inline=False,
    )
    embed.add_field(
        name="2 — Fill the form",
        value=(
            "• **Source links** — a ZIP/CBZ URL, or direct image URLs "
            "(one per line or comma-separated)\n"
            "• **Work name** — e.g. `solo-leveling`\n"
            "• **Chapter number** — e.g. `12`\n"
            f"• **JPEG quality** — optional, 1-100 (default {config.JPEG_QUALITY})"
        ),
        inline=False,
    )
    embed.add_field(
        name="3 — Wait",
        value=(
            "The bot downloads your images, uploads them to storage, and runs the GPU job. "
            "Progress is shown live in the message."
        ),
        inline=False,
    )
    embed.add_field(
        name="4 — Download",
        value=(
            "When finished, a **⬇️ Download ZIP** button appears. "
            f"The link stays valid for **{config.LINK_EXPIRE_HOURS // 24} days**."
        ),
        inline=False,
    )
    embed.add_field(
        name="Limits",
        value=(
            f"• Max download size: 500MB per link\n"
            f"• Max concurrent jobs: {config.MAX_CONCURRENT_JOBS}\n"
            f"• Job timeout: {config.JOB_TIMEOUT_MINUTES} minutes"
        ),
        inline=False,
    )
    return embed
