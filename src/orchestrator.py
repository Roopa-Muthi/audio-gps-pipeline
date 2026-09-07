"""
Sprint 3 — Orchestrator + latency budget

Runs the audio stream and GPS stream concurrently. On each new transcript,
it pairs the transcript with the most recent GPS fix, then runs the
cache -> LLM-parse -> fallback chain, and enforces a sub-400ms budget on
that whole per-event pipeline using asyncio.wait_for. A miss of the budget
degrades to the fallback parser rather than blocking indefinitely.
"""
import asyncio
import time

from src.audio_stream import AudioStreamer
from src.config import settings
from src.gps_tracker import GpsTracker, GpsFix
from src.conversation_parser import parse_transcript
from src.fallback import local_parse
from src.schemas import ConversationEvent
from src.security import sha256_checksum
from src.semantic_cache import SemanticCache


class Orchestrator:
    def __init__(self):
        self.audio = AudioStreamer()
        self.gps = GpsTracker()
        self.cache = SemanticCache()
        self._latest_fix: GpsFix | None = None
        self._latency_budget = settings.latency_budget_ms / 1000.0

    async def _gps_loop(self):
        async for fix in self.gps.stream_fixes():
            self._latest_fix = fix

    async def _handle_transcript(self, transcript: str) -> ConversationEvent:
        start = time.perf_counter()
        lat = self._latest_fix.lat if self._latest_fix else None
        lon = self._latest_fix.lon if self._latest_fix else None

        cached = self.cache.lookup(transcript)
        if cached is not None:
            return cached

        try:
            event = await asyncio.wait_for(
                parse_transcript(transcript, lat=lat, lon=lon),
                timeout=self._latency_budget,
            )
            if event is None:
                raise ValueError("parser returned no valid event")
        except (asyncio.TimeoutError, ValueError, Exception) as exc:
            print(f"[orchestrator] falling back on-device: {type(exc).__name__}: {exc}")
            event = local_parse(transcript, lat=lat, lon=lon)

        self.cache.store(transcript, event)

        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[orchestrator] event resolved in {elapsed_ms:.1f}ms "
              f"(budget {settings.latency_budget_ms}ms) source={event.source}")
        return event

    async def _audio_loop(self, on_event):
        async for transcript in self.audio.stream_transcripts():
            event = await self._handle_transcript(transcript)
            payload = event.model_dump()
            payload["checksum"] = sha256_checksum(payload)
            await on_event(event)

    async def run(self, on_event):
        self.audio.start()
        try:
            await asyncio.gather(self._gps_loop(), self._audio_loop(on_event))
        finally:
            self.audio.stop()
