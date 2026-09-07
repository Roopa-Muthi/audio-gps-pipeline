"""
Demo entrypoint. Run with: python -m src.main
Speak into the mic; each resolved conversation event is printed and shipped
to S3 with its SHA-256 checksum.
"""
import asyncio

from src.orchestrator import Orchestrator
from src.s3_storage import upload_event


async def on_event(event):
    print(f"-> {event.model_dump()}")
    try:
        key = await upload_event(event)
        print(f"   uploaded to s3://.../{key}")
    except Exception as exc:
        print(f"   [s3 upload skipped] {exc}")


async def main():
    orchestrator = Orchestrator()
    print("Listening... (Ctrl+C to stop)")
    await orchestrator.run(on_event)


if __name__ == "__main__":
    asyncio.run(main())
