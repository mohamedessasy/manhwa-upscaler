"""Collect source images from user input: direct URLs, ZIP/CBZ links, one or many.

No gdown, no Google Drive scraping — that was the #1 failure source in the old bot.
Returns list[(filename, bytes)] in natural order; count is preserved downstream.
"""
import io
import re
import zipfile

import aiohttp

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
ZIP_EXTS = (".zip", ".cbz")

MAX_DOWNLOAD_MB = 500


def natural_key(name: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def parse_urls(source: str) -> list[str]:
    """Split on newlines / commas / whitespace, keep only http(s) urls."""
    parts = re.split(r"[\s,]+", source.strip())
    return [p for p in parts if p.startswith(("http://", "https://"))]


def _extract_zip(data: bytes) -> list[tuple[str, bytes]]:
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = sorted(
        (n for n in zf.namelist()
         if n.lower().endswith(IMG_EXTS) and not n.startswith("__MACOSX")),
        key=natural_key,
    )
    return [(n.rsplit("/", 1)[-1], zf.read(n)) for n in names]


async def _fetch_raw(session: aiohttp.ClientSession, url: str,
                     params: dict | None = None) -> tuple[bytes, str]:
    async with session.get(url, params=params,
                           timeout=aiohttp.ClientTimeout(total=300)) as r:
        r.raise_for_status()
        limit = MAX_DOWNLOAD_MB * 1024 * 1024
        size = int(r.headers.get("Content-Length") or 0)
        if size > limit:
            raise ValueError(f"file too large: {size / 1e6:.0f}MB > {MAX_DOWNLOAD_MB}MB")
        data = await r.read()
        if len(data) > limit:  # header may be missing/lying
            raise ValueError(f"file too large: {len(data) / 1e6:.0f}MB > {MAX_DOWNLOAD_MB}MB")
        ctype = r.headers.get("Content-Type", "").lower()
    return data, ctype


# ---- Google Drive (single files, e.g. an uploaded chapter ZIP) ----
GDRIVE_FOLDER_MARKER = "drive.google.com/drive/folders"


def _gdrive_file_id(url: str) -> str | None:
    if "drive.google.com" not in url and "drive.usercontent.google.com" not in url:
        return None
    for pat in (r"/file/d/([\w-]{20,})", r"[?&]id=([\w-]{20,})"):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _fetch(session: aiohttp.ClientSession, url: str) -> tuple[bytes, str]:
    if GDRIVE_FOLDER_MARKER in url:
        raise ValueError(
            "Google Drive *folder* links are not supported — "
            "upload the chapter as a single ZIP file and share that instead"
        )

    fid = _gdrive_file_id(url)
    if fid:
        url = f"https://drive.google.com/uc?export=download&id={fid}"

    data, ctype = await _fetch_raw(session, url)

    if fid and "text/html" in ctype:
        # Large files: Google returns a virus-scan confirmation page.
        # Parse the download form (drive.usercontent.google.com) and follow it.
        html = data.decode("utf-8", "ignore")
        m = re.search(r'<form[^>]+action="([^"]+)"', html)
        if not m:
            raise ValueError(
                "Google Drive refused the download — make sure the file is shared "
                "as 'Anyone with the link'"
            )
        action = m.group(1).replace("&amp;", "&")
        params = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', html))
        data, ctype = await _fetch_raw(session, action, params=params)
        if "text/html" in ctype:
            raise ValueError(
                "Google Drive download failed — check the sharing permissions "
                "('Anyone with the link')"
            )

    return data, ctype


async def collect(source: str, progress_cb=None) -> list[tuple[str, bytes]]:
    urls = parse_urls(source)
    if not urls:
        raise ValueError("no valid http(s) URLs found in input")

    images: list[tuple[str, bytes]] = []
    async with aiohttp.ClientSession() as session:
        total = len(urls)
        for i, url in enumerate(urls, start=1):
            data, ctype = await _fetch(session, url)
            path = url.split("?")[0].lower()

            if path.endswith(ZIP_EXTS) or "zip" in ctype:
                images.extend(_extract_zip(data))
            elif path.endswith(IMG_EXTS) or ctype.startswith("image/"):
                name = path.rsplit("/", 1)[-1] or f"img_{i}"
                images.append((name, data))
            else:
                # last resort: try zip then assume image
                try:
                    images.extend(_extract_zip(data))
                except zipfile.BadZipFile:
                    images.append((f"img_{i}", data))

            if progress_cb:
                await progress_cb(i, total)

    return images


def build_input_zip(images: list[tuple[str, bytes]]) -> bytes:
    """Pack collected images into one zip, preserving order via numbered names."""
    pad = max(2, len(str(len(images))))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for i, (name, data) in enumerate(images, start=1):
            ext = name.rsplit(".", 1)[-1] if "." in name else "png"
            zf.writestr(f"{i:0{pad}d}.{ext}", data)
    return buf.getvalue()
