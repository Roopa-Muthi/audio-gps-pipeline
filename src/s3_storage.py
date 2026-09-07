"""
Sprint 6 — S3 storage

Uploads each ConversationEvent as JSON alongside its SHA-256 checksum, keyed
by timestamp, to the configured S3 bucket. Uses boto3's default sync client
in a thread pool so it doesn't block the event loop either.
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import boto3

from src.config import settings
from src.schemas import ConversationEvent
from src.security import sha256_checksum

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="s3-upload")


def _get_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def _upload_blocking(event: ConversationEvent) -> str:
    payload = event.model_dump()
    checksum = sha256_checksum(payload)
    body = json.dumps({"payload": payload, "sha256": checksum}).encode("utf-8")

    key = f"conversation-events/{int(payload['timestamp'] * 1000)}.json"
    client = _get_client()
    client.put_object(Bucket=settings.s3_bucket_name, Key=key, Body=body, ContentType="application/json")
    return key


async def upload_event(event: ConversationEvent) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _upload_blocking, event)
