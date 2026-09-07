"""
Sprint 5 — On-device fallback

If the LangGraph/LLM path fails (network down, API error, timeout, or
exhausted retries), this keyword-based parser keeps the pipeline producing
schema-valid output instead of dropping the event entirely. Lower fidelity,
but it keeps the sub-400ms budget since there's no network round trip.
"""
import time

from src.schemas import ConversationEvent

_INTENT_KEYWORDS = {
    "navigate": ["navigate", "directions", "route", "take me", "drive to"],
    "query": ["what", "how far", "distance", "where is", "eta"],
    "command": ["stop", "pause", "start", "cancel", "mute"],
}


def local_parse(transcript: str, lat: float = None, lon: float = None) -> ConversationEvent:
    text_lower = transcript.lower()
    intent = "chat"
    for candidate_intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            intent = candidate_intent
            break

    return ConversationEvent(
        transcript=transcript,
        intent=intent,
        entities={},
        lat=lat,
        lon=lon,
        timestamp=time.time(),
        source="fallback",
    )
