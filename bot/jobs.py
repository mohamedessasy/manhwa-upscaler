"""Job pipeline: collect -> upload to R2 -> RunPod -> progress -> result links."""
import asyncio
import time
import traceback
import uuid

import discord

import config
import r2
import runpod_client
import sources

_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)

COLOR_DL = 0x3498DB
COLOR_UP = 0xF1C40F
COLOR_GPU = 0x9B59B6
COLOR_OK = 0x2ECC71
COLOR_ERR = 0xE74C3C


def progress_bar(done: int, total: int, length: int = 18) -> str:
    ratio = max(0.0, min(1.0, done / total if total else 0.0))
    full = int(ratio * length)
    return "▓" * full + "░" * (length - full) + f" {int(ratio * 100)}%"


class StatusMessage:
    """Throttled embed editor so we never hit Discord rate limits."""

    def __init__(self, message: discord.Message, header: str):
        self.message = message
        self.header = header
        self._last_edit = 0.0

    async def update(self, title: str, desc: str, color: int, force: bool = False):
        now = time.monotonic()
        if not force and now - self._last_edit < 2.0:
            return
        self._last_edit = now
        embed = discord.Embed(title=title, description=f"{self.header}\n\n{desc}", color=color)
        try:
            await self.message.edit(embed=embed, view=None)
        except discord.HTTPException:
            pass

    async def done(self, embed: discord.Embed, view: discord.ui.View | None = None):
        try:
            await self.message.edit(embed=embed, view=view)
        except discord.HTTPException:
            pass


async def run_job(message: discord.Message, source: str, work_name: str,
                  chapter: str, quality: int):
    job_id = uuid.uuid4().hex[:12]
    header = f"**{work_name} / {chapter}** · `{job_id}`"
    status = StatusMessage(message, header)

    async with _semaphore:
        try:
            # 1 -- download sources
            await status.update("📥 تحميل الصور", "جاري البدء...", COLOR_DL, force=True)

            async def on_dl(done, total):
                await status.update("📥 تحميل الصور",
                                    f"تحميل **{done}/{total}**\n{progress_bar(done, total)}",
                                    COLOR_DL)

            images = await sources.collect(source, progress_cb=on_dl)
            if not images:
                await status.update("❌ لا توجد صور", "تأكد من الرابط.", COLOR_ERR, force=True)
                return
            total = len(images)

            # 2 -- upload input zip to R2
            await status.update("☁️ رفع المدخلات", f"رفع **{total}** صورة إلى التخزين...",
                                COLOR_UP, force=True)
            input_key = f"jobs/{job_id}/in.zip"
            out_prefix = f"jobs/{job_id}/out"
            zip_bytes = sources.build_input_zip(images)
            await asyncio.to_thread(r2.upload_bytes, input_key, zip_bytes, "application/zip")

            # 3 -- submit to RunPod serverless (GPU spins up on demand)
            await status.update("🚀 تشغيل الـGPU", "إرسال المهمة إلى RunPod...", COLOR_GPU, force=True)
            rp_id = await runpod_client.submit({
                "input_key": input_key,
                "out_prefix": out_prefix,
                "out_width": config.OUT_WIDTH,
                "quality": quality,
            })

            # 4 -- watch progress
            result = None
            async for st in runpod_client.watch(rp_id, timeout_minutes=config.JOB_TIMEOUT_MINUTES):
                s = st.get("status")
                if s == "IN_QUEUE":
                    await status.update("⏳ في الانتظار", "الـGPU يعمل الآن (cold start)...", COLOR_GPU)
                elif s == "IN_PROGRESS":
                    prog = st.get("output")
                    if isinstance(prog, str) and "/" in prog:
                        done, tot = prog.split("/", 1)
                        try:
                            d, t = int(done), int(tot)
                            await status.update("🎨 جاري الـUpscale",
                                                f"معالجة **{d}/{t}**\n{progress_bar(d, t)}",
                                                COLOR_UP)
                        except ValueError:
                            pass
                    else:
                        await status.update("🎨 جاري الـUpscale", "المعالجة على الـGPU...", COLOR_UP)
                elif s == "COMPLETED":
                    result = st.get("output") or {}
                elif s in ("FAILED", "CANCELLED", "TIMED_OUT"):
                    err = st.get("error") or s
                    await status.update("❌ فشلت المهمة", f"```{str(err)[:900]}```", COLOR_ERR, force=True)
                    return

            if not result or result.get("error"):
                await status.update("❌ فشلت المهمة",
                                    str((result or {}).get("error", "نتيجة فارغة"))[:900],
                                    COLOR_ERR, force=True)
                return

            # 5 -- final links
            zip_key = result["zip_key"]
            count = result.get("count", total)
            zip_url = await asyncio.to_thread(r2.presign, zip_key)

            embed = discord.Embed(
                title="✅ اكتمل!",
                description=(
                    f"{header}\n\n"
                    f"عدد الصور: **{count}** (بدون تغيير)\n"
                    f"العرض: **{config.OUT_WIDTH}px** · JPEG جودة **{quality}**\n"
                    f"الرابط صالح لمدة **{config.LINK_EXPIRE_HOURS // 24} أيام**"
                ),
                color=COLOR_OK,
            )
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(label="⬇️ تحميل ZIP", url=zip_url))
            await status.done(embed, view)

            # cleanup input zip only (outputs stay until lifecycle rule deletes them)
            await asyncio.to_thread(r2.delete_prefix, input_key)

        except Exception as e:
            traceback.print_exc()
            await status.update("❌ خطأ غير متوقع", f"```{str(e)[:900]}```", COLOR_ERR, force=True)
