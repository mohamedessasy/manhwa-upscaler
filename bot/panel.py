"""Button panel + modal — the main UI. Persistent across bot restarts."""
import asyncio

import discord

import config
import jobs


class UpscaleModal(discord.ui.Modal, title="Upscale — مانهوا"):
    source = discord.ui.TextInput(
        label="الروابط (صور / ZIP)",
        style=discord.TextStyle.paragraph,
        placeholder="رابط ZIP أو روابط صور (كل رابط في سطر أو مفصولة بفواصل)",
        required=True,
        max_length=4000,
    )
    work_name = discord.ui.TextInput(
        label="اسم العمل",
        placeholder="مثال: solo-leveling",
        required=True,
        max_length=100,
    )
    chapter = discord.ui.TextInput(
        label="رقم الفصل",
        placeholder="مثال: 12",
        required=True,
        max_length=20,
    )
    quality = discord.ui.TextInput(
        label=f"جودة JPEG (اختياري، الافتراضي {config.JPEG_QUALITY})",
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
            title="🕐 بدء المهمة...",
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


def panel_embed() -> discord.Embed:
    return discord.Embed(
        title="🖼️ Manhwa Upscaler",
        description=(
            "اضغط **⚡ Upscale** وحط الرابط واسم العمل ورقم الفصل.\n\n"
            "**المصادر المدعومة:**\n"
            "• رابط ZIP / CBZ\n"
            "• روابط صور مباشرة (سطر لكل رابط)\n\n"
            f"**الإخراج:** عرض {config.OUT_WIDTH}px · JPEG · نفس عدد الصور وترتيبها"
        ),
        color=0x5865F2,
    )
