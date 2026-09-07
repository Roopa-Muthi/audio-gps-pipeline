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
