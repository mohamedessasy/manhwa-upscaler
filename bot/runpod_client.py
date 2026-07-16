"""Async client for RunPod Serverless (/run + /status polling)."""
import asyncio

import aiohttp

import config

BASE = f"https://api.runpod.ai/v2/{config.RUNPOD_ENDPOINT_ID}"
HEADERS = {"Authorization": f"Bearer {config.RUNPOD_API_KEY}"}


async def submit(payload: dict) -> str:
    """Submit an async job, return runpod job id."""
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        async with s.post(f"{BASE}/run", json={"input": payload}) as r:
            r.raise_for_status()
            data = await r.json()
    return data["id"]


async def watch(job_id: str, interval: float = 4.0, timeout_minutes: int = 30):
    """Yield status dicts until the job reaches a terminal state."""
    deadline = asyncio.get_event_loop().time() + timeout_minutes * 60
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        while True:
            async with s.get(f"{BASE}/status/{job_id}") as r:
                r.raise_for_status()
                st = await r.json()
            yield st
            if st.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                return
            if asyncio.get_event_loop().time() > deadline:
                st["status"] = "TIMED_OUT"
                yield st
                return
            await asyncio.sleep(interval)


async def cancel(job_id: str):
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        await s.post(f"{BASE}/cancel/{job_id}")
