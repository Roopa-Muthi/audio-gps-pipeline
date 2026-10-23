"""
Demo entrypoint. Run with: python -m src.main
Opens the dashboard at http://127.0.0.1:8000 and starts listening on the mic.
Each resolved conversation event is pushed live to any open dashboard tab,
printed, and shipped to S3 with its SHA-256 checksum.
"""
import asyncio

import uvicorn

from src.orchestrator import Orchestrator
from src.s3_storage import upload_event
from src.web_server import app, broadcast_event


async def on_event(event, latency_ms: float):
    payload = event.model_dump()
    payload["latency_ms"] = round(latency_ms, 1)
    print(f"-> {payload}")

    await broadcast_event(payload)

    try:
        key = await upload_event(event)
        print(f"   uploaded to s3://.../{key}")
    except Exception as exc:
        print(f"   [s3 upload skipped] {exc}")


async def run_dashboard():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    orchestrator = Orchestrator()
    print("Dashboard: http://127.0.0.1:8000")
    print("Listening... (Ctrl+C to stop)")
    await asyncio.gather(
        run_dashboard(),
        orchestrator.run(on_event),
    )


if __name__ == "__main__":
    asyncio.run(main())
