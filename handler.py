"""RunPod Serverless handler.

Job input:
{
  "input_key":  "jobs/<id>/in.zip",   # zip of source images in R2
  "out_prefix": "jobs/<id>/out",      # where results go in R2
  "out_width":  800,                  # final width (site requirement)
  "quality":    85,                   # JPEG quality
}

Each page: upscale (GPU) -> resize to out_width -> JPEG.
Page count and order are NEVER changed.
"""
import io
import os
import re
import zipfile

import boto3
import runpod
from PIL import Image

from upscale import Upscaler

IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)
BUCKET = os.environ["R2_BUCKET"]

# Loaded once per worker => warm requests skip model load entirely.
upscaler = Upscaler(
    model_path=os.getenv("MODEL_PATH", "/models/model.pth"),
    tile=int(os.getenv("TILE_SIZE", "512")),
)


def natural_key(name: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def handler(job):
    inp = job["input"]
    input_key = inp["input_key"]
    out_prefix = inp["out_prefix"].rstrip("/")
    out_width = int(inp.get("out_width", 800))
    quality = int(inp.get("quality", 85))

    # -- download input zip from R2
    buf = io.BytesIO()
    s3.download_fileobj(BUCKET, input_key, buf)
    zf = zipfile.ZipFile(buf)
    names = sorted(
        (n for n in zf.namelist()
         if n.lower().endswith(IMG_EXTS) and not n.startswith("__MACOSX")),
        key=natural_key,
    )
    total = len(names)
    if total == 0:
        return {"error": "no images found in input zip"}

    pad = max(2, len(str(total)))
    out_zip_buf = io.BytesIO()
    out_zip = zipfile.ZipFile(out_zip_buf, "w", zipfile.ZIP_STORED)

    for i, name in enumerate(names, start=1):
        img = Image.open(io.BytesIO(zf.read(name))).convert("RGB")

        up = upscaler.upscale(img)

        # site requirement: final width is exactly out_width
        if up.width != out_width:
            new_h = max(1, round(up.height * out_width / up.width))
            up = up.resize((out_width, new_h), Image.LANCZOS)

        ob = io.BytesIO()
        up.save(ob, "JPEG", quality=quality, optimize=True)
        data = ob.getvalue()

        fname = f"{i:0{pad}d}.jpg"
        s3.put_object(
            Bucket=BUCKET, Key=f"{out_prefix}/{fname}",
            Body=data, ContentType="image/jpeg",
        )
        out_zip.writestr(fname, data)
        runpod.serverless.progress_update(job, f"{i}/{total}")

    out_zip.close()
    zip_key = f"{out_prefix}.zip"
    s3.put_object(
        Bucket=BUCKET, Key=zip_key,
        Body=out_zip_buf.getvalue(), ContentType="application/zip",
    )
    return {"count": total, "out_prefix": out_prefix, "zip_key": zip_key}


runpod.serverless.start({"handler": handler})
