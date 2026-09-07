"""
Sprint 0 — Setup
Central place to load configuration from environment variables so nothing
is hardcoded across the pipeline modules.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    latency_budget_ms: int = int(os.getenv("LATENCY_BUDGET_MS", "400"))
    audio_chunk_seconds: float = float(os.getenv("AUDIO_CHUNK_SECONDS", "2"))
    gps_emit_interval_seconds: float = float(os.getenv("GPS_EMIT_INTERVAL_SECONDS", "1"))
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "base")


settings = Settings()
