"""
Sprint 4 — Validated JSON schema

Every parsed conversation event must conform to this schema before it's
cached, signed, or uploaded. Invalid output triggers the retry/fallback path
instead of ever reaching storage.
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ConversationEvent(BaseModel):
    transcript: str = Field(..., min_length=1)
    intent: str = Field(..., description="Best-guess user intent, e.g. 'navigate', 'query', 'chat'")
    entities: dict[str, str] = Field(default_factory=dict)
    lat: Optional[float] = None
    lon: Optional[float] = None
    timestamp: float
    source: str = Field(default="llm", description="'llm' or 'fallback'")

    @field_validator("lat")
    @classmethod
    def lat_in_range(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("lat out of range")
        return v

    @field_validator("lon")
    @classmethod
    def lon_in_range(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("lon out of range")
        return v
