"""
Sprint 1 — Audio streaming + STT

Captures microphone audio on a background thread (so it never blocks the
asyncio event loop) and runs local Whisper transcription in a
ThreadPoolExecutor, since faster-whisper's `.transcribe()` call is
blocking/CPU-bound.
"""
import asyncio
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from src.config import settings

SAMPLE_RATE = 16_000


class AudioStreamer:
    def __init__(self, model_size: str = None, executor: ThreadPoolExecutor = None):
        self._model_size = model_size or settings.whisper_model_size
        self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        self._audio_q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper")
        self._stop_event = threading.Event()

    # ---- mic capture thread ----
    def _mic_callback(self, indata, frames, time_info, status):
        if status:
            # Non-fatal driver warnings (buffer underrun etc.) — log, don't crash the stream
            print(f"[audio] sounddevice status: {status}")
        self._audio_q.put(indata.copy())

    def _capture_thread(self):
        chunk_frames = int(SAMPLE_RATE * settings.audio_chunk_seconds)
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=chunk_frames,
            callback=self._mic_callback,
        ):
            while not self._stop_event.is_set():
                threading.Event().wait(0.05)

    def start(self):
        self._thread = threading.Thread(target=self._capture_thread, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _transcribe_blocking(self, audio_chunk: np.ndarray) -> str:
        audio_flat = audio_chunk.flatten().astype(np.float32)
        segments, _ = self._model.transcribe(
            audio_flat,
            language="en",
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def stream_transcripts(self) -> AsyncGenerator[str, None]:
        """Yields transcript strings as chunks become available, without blocking the loop."""
        loop = asyncio.get_event_loop()
        while not self._stop_event.is_set():
            try:
                chunk = self._audio_q.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue

            text = await loop.run_in_executor(self._executor, self._transcribe_blocking, chunk)
            if text:
                yield text
