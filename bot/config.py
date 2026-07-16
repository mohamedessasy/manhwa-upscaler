"""All secrets come from environment variables — nothing hardcoded."""
import os

from dotenv import load_dotenv

load_dotenv()

# ===== Discord =====
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

# ===== Cloudflare R2 =====
R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]

# ===== RunPod Serverless =====
RUNPOD_API_KEY = os.environ["RUNPOD_API_KEY"]
RUNPOD_ENDPOINT_ID = os.environ["RUNPOD_ENDPOINT_ID"]

# ===== Output (site requirements) =====
OUT_WIDTH = int(os.getenv("OUT_WIDTH", "800"))          # final image width
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "85"))      # default JPEG quality
LINK_EXPIRE_HOURS = int(os.getenv("LINK_EXPIRE_HOURS", "168"))  # presigned link ttl (max 7 days)

# ===== Limits =====
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
JOB_TIMEOUT_MINUTES = int(os.getenv("JOB_TIMEOUT_MINUTES", "30"))
