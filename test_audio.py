import asyncio
from src.audio_stream import AudioStreamer

async def main():
    streamer = AudioStreamer()
    streamer.start()
    print("Listening... speak into your mic (Ctrl+C to stop)")
    async for text in streamer.stream_transcripts():
        print("Transcript:", text)

asyncio.run(main())