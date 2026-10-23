"""
Sprint 3 acceptance test.

Verifies that when the LLM parse step is slow/unavailable, the orchestrator
still resolves an event within the configured latency budget by falling
back on-device, rather than hanging.
"""
import asyncio
from unittest.mock import patch

import pytest

from src.orchestrator import Orchestrator
from src.config import settings


async def _slow_parse(*args, **kwargs):
    await asyncio.sleep(5)  # deliberately exceeds the budget
    return None


@pytest.mark.asyncio
async def test_falls_back_within_latency_budget():
    orchestrator = Orchestrator()

    with patch("src.orchestrator.parse_transcript", _slow_parse):
        start = asyncio.get_event_loop().time()
        event, elapsed_ms = await orchestrator._handle_transcript("navigate to the station")
        elapsed_ms_check = (asyncio.get_event_loop().time() - start) * 1000

    assert event.source == "fallback"
    # small margin over the budget to allow for scheduling overhead
    assert elapsed_ms_check < settings.latency_budget_ms + 100


@pytest.mark.asyncio
async def test_semantic_cache_hit_skips_reparse():
    orchestrator = Orchestrator()
    first, _ = await orchestrator._handle_transcript("what is the distance to the station")
    orchestrator.cache.store("what is the distance to the station", first)

    with patch("src.orchestrator.parse_transcript") as mock_parse:
        second, _ = await orchestrator._handle_transcript("how far is the station")
        assert mock_parse.await_count == 0  # semantic hit, no LLM call
        assert second.intent == first.intent
