# Async Audio + GPS Pipeline (Sub-400ms) — GenAI Conversation Parser

A resume-showcase project: an async, multi-threaded Python pipeline that orchestrates
parallel audio streaming + GPS tracking, transcribes speech with Whisper, parses live
conversation into validated JSON with LangGraph, semantically caches repeated queries,
falls back on-device when the network/API is unavailable, and ships everything to S3
behind a SHA-256 integrity check.

## Architecture

```
 ┌─────────────┐     ┌──────────────┐
 │ Audio Stream │     │ GPS Tracker  │   (run concurrently, asyncio.gather)
 │ (thread pool │     │ (async task) │
 │  + Whisper)  │     └──────┬───────┘
 └──────┬───────┘            │
        │ transcript          │ coords
        ▼                     ▼
      ┌───────────────────────────┐
      │   Orchestrator (asyncio)  │  <-- sub-400ms budget per tick
      └──────────┬─────────────────┘
                 ▼
      ┌───────────────────────────┐
      │  Semantic Cache lookup     │──hit──> return cached JSON
      └──────────┬─────────────────┘
                 │ miss
                 ▼
      ┌───────────────────────────┐
      │ LangGraph Conversation     │──fails──> On-device fallback
      │ Parser -> Pydantic schema  │           (local rules/small model)
      └──────────┬─────────────────┘
                 ▼
      ┌───────────────────────────┐
      │ SHA-256 sign + S3 upload   │
      └───────────────────────────┘
```

## Agile sprint breakdown

**Sprint 0 — Setup (0.5 day)**
- Repo scaffold, virtualenv, `requirements.txt`, config, S3 bucket (free tier), AWS credentials via `.env`.

**Sprint 1 — Audio streaming + STT (2 days)**
- `audio_stream.py`: mic capture on its own thread (never block the event loop), chunked buffering, local Whisper (`faster-whisper`) transcription.
- Acceptance: mic audio → text transcript printed within one buffer cycle.

**Sprint 2 — GPS tracking (1 day)**
- `gps_tracker.py`: async task emitting simulated (or serial-fed real) GPS coords on a timer, mocked-first so Sprint 3+ isn't blocked by hardware.
- Acceptance: coordinate stream runs concurrently with audio without stalling it.

**Sprint 3 — Orchestrator + latency budget (2 days)**
- `orchestrator.py`: `asyncio.gather` over audio + GPS + parser, per-tick deadline enforcement (sub-400ms), thread pool executor for the blocking Whisper call.
- Acceptance: `tests/test_latency.py` asserts p95 tick latency < 400ms on sample audio.

**Sprint 4 — LangGraph parsing + schemas (2 days)**
- `schemas.py` (Pydantic), `conversation_parser.py` (LangGraph state graph: transcript → intent extraction → schema validation → retry-on-invalid node).
- Acceptance: garbled/partial transcript still resolves to a schema-valid JSON object or a typed error.

**Sprint 5 — Semantic cache + on-device fallback (1.5 days)**
- `semantic_cache.py`: embedding similarity cache (cosine sim over sentence embeddings) to skip repeat LLM calls.
- `fallback.py`: if the LLM call fails/times out, run a lightweight local rule-based/keyword parser so the pipeline degrades instead of crashing.
- Acceptance: killing network mid-run still yields a (lower-fidelity) JSON result.

**Sprint 6 — Security + S3 + wrap-up (1 day)**
- `security.py`: SHA-256 checksum per payload, stored alongside the object for integrity verification.
- `s3_storage.py`: upload JSON + checksum to S3.
- README, load test, demo script (`main.py`), retro notes.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m src.main
```

## Run tests

```bash
pytest tests/ -v
```
