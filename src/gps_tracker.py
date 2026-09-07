"""
Sprint 2 — GPS tracking

Emits (lat, lon, timestamp) on a fixed interval as an async generator, so it
runs concurrently with audio streaming via asyncio.gather in the orchestrator.

Simulated by default (random walk around a start point) so development isn't
blocked on real GPS hardware. Swap `_read_real_gps()` in for a serial/NMEA
feed when hardware is available — the orchestrator doesn't need to change.
"""
import asyncio
import random
import time
from dataclasses import dataclass
from typing import AsyncGenerator

from src.config import settings


@dataclass
class GpsFix:
    lat: float
    lon: float
    timestamp: float


class GpsTracker:
    def __init__(self, start_lat: float = 17.3850, start_lon: float = 78.4867):
        # Defaults to Hyderabad coordinates as a sane starting point
        self._lat = start_lat
        self._lon = start_lon

    def _simulate_step(self) -> GpsFix:
        # Small random walk to mimic a moving device
        self._lat += random.uniform(-0.0003, 0.0003)
        self._lon += random.uniform(-0.0003, 0.0003)
        return GpsFix(lat=round(self._lat, 6), lon=round(self._lon, 6), timestamp=time.time())

    async def _read_real_gps(self) -> GpsFix:
        """Placeholder for real hardware: read + parse an NMEA sentence from a serial port."""
        raise NotImplementedError("Wire this up to your GPS module's serial feed")

    async def stream_fixes(self, use_real_gps: bool = False) -> AsyncGenerator[GpsFix, None]:
        while True:
            if use_real_gps:
                fix = await self._read_real_gps()
            else:
                fix = self._simulate_step()
            yield fix
            await asyncio.sleep(settings.gps_emit_interval_seconds)
