"""Cloudflare R2 (S3-compatible) helpers. boto3 is blocking -> call via asyncio.to_thread."""
import boto3
from botocore.config import Config

import config

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
    return _client


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream"):
    client().put_object(Bucket=config.R2_BUCKET, Key=key, Body=data, ContentType=content_type)


def presign(key: str, expires_hours: int | None = None) -> str:
    expires = (expires_hours or config.LINK_EXPIRE_HOURS) * 3600
    return client().generate_presigned_url(
        "get_object",
        Params={"Bucket": config.R2_BUCKET, "Key": key},
        ExpiresIn=min(expires, 7 * 24 * 3600),  # SigV4 hard limit: 7 days
    )


def delete_prefix(prefix: str):
    """Best-effort cleanup of a job's files."""
    c = client()
    resp = c.list_objects_v2(Bucket=config.R2_BUCKET, Prefix=prefix)
    keys = [{"Key": o["Key"]} for o in resp.get("Contents", [])]
    if keys:
        c.delete_objects(Bucket=config.R2_BUCKET, Delete={"Objects": keys})
