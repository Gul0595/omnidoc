"""
tools/storage.py — Cloudflare R2 storage with local fallback

# ── CREDENTIAL REQUIRED ──────────────────────────────────────────────────────
# R2_ACCOUNT_ID      — Cloudflare dashboard → Account ID
# R2_ACCESS_KEY_ID   — R2 → Manage API Tokens
# R2_SECRET_ACCESS_KEY
# R2_BUCKET_NAME     — your bucket name
# Get R2 free (10GB): https://dash.cloudflare.com → R2
# ─────────────────────────────────────────────────────────────────────────────
# If R2 not configured, files saved locally to ./data/uploads/
"""
import os
from pathlib import Path

LOCAL = Path("./data/uploads")
LOCAL.mkdir(parents=True, exist_ok=True)


def _client():
    try:
        import boto3
        from botocore.config import Config
        aid = os.getenv("R2_ACCOUNT_ID")
        if not aid:
            return None
        return boto3.client(
            "s3",
            endpoint_url=f"https://{aid}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    except Exception:
        return None


def upload_bytes(data: bytes, key: str) -> bool:
    client = _client()
    if client:
        try:
            client.put_object(
                Bucket=os.getenv("R2_BUCKET_NAME", "omnidoc-files"),
                Key=key, Body=data)
            return True
        except Exception as e:
            print(f"R2 upload failed: {e} — saving locally")
    dest = LOCAL / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def download_bytes(key: str) -> bytes | None:
    client = _client()
    if client:
        try:
            r = client.get_object(
                Bucket=os.getenv("R2_BUCKET_NAME", "omnidoc-files"), Key=key)
            return r["Body"].read()
        except Exception:
            pass
    local = LOCAL / key
    return local.read_bytes() if local.exists() else None
