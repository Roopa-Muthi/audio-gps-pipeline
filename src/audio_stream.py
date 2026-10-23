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
from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

from src.config import settings

SAMPLE_RATE = 16_000

# Maps Whisper's detected/forced language code to the transliteration
# library's script constant. Urdu isn't included — it's Perso-Arabic script,
# a different family this library doesn't handle well.
_SCRIPT_MAP = {
    "te": sanscript.TELUGU,
    "hi": sanscript.DEVANAGARI,
    "mr": sanscript.DEVANAGARI,
    "ta": sanscript.TAMIL,
    "kn": sanscript.KANNADA,
    "ml": sanscript.MALAYALAM,
    "bn": sanscript.BENGALI,
    "gu": sanscript.GUJARATI,
    "pa": sanscript.GURMUKHI,
    "or": sanscript.ORIYA,
}


def _romanize(text: str, lang_code: str) -> str:
    """Phonetic script-to-Latin conversion — NOT translation. 'నేను' becomes
    'nenu', not 'I'. English text (or any unmapped language) passes through
    unchanged."""
    scheme = _SCRIPT_MAP.get(lang_code)
    if not scheme:
        return text
    try:
        return transliterate(text, scheme, sanscript.ITRANS)
    except Exception:
        return text


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
        # Empty WHISPER_LANGUAGE means "auto-detect this chunk's language";
        # a specific ISO code (e.g. "te") skips detection and forces that language.
        forced_language = settings.whisper_language or None
        try:
            segments, info = self._model.transcribe(
                audio_flat,
                language=forced_language,
                beam_size=1,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=False,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
        except ValueError:
            # faster-whisper's auto-detect step can crash internally when VAD
            # strips a chunk down to pure silence/noise, leaving nothing to
            # detect a language from. Treat it as "no speech," not a crash.
            return ""

        if not text:
            return ""

        detected_lang = forced_language or info.language
        if forced_language is None:
            print(f"[audio] detected language: {detected_lang} (confidence {info.language_probability:.2f})")

        return _romanize(text, detected_lang)

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
