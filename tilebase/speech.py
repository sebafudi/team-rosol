"""Streaming speech-to-text. Mic audio goes to Deepgram; transcripts come back live."""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd
import websockets

SAMPLE_RATE = 16_000
CHANNELS = 1
FRAME_SAMPLES = 1_600
LISTEN_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3"
    "&encoding=linear16"
    "&sample_rate=16000"
    "&channels=1"
    "&interim_results=true"
    "&endpointing=500"
    "&punctuate=true"
    "&smart_format=true"
)


@dataclass(frozen=True)
class Transcript:
    text: str
    final: bool


@dataclass(frozen=True)
class ListenError:
    message: str


def api_key() -> str | None:
    for name in ("DEEPGRAM_API_KEY", "DEEPGRAM_APIKEY"):
        value = os.environ.get(name)
        if value:
            return value
    env_file = Path(__file__).resolve().parents[1] / ".env.local"
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() in ("DEEPGRAM_API_KEY", "DEEPGRAM_APIKEY"):
            return value.strip().strip('"').strip("'")
    return None


async def listen() -> AsyncIterator[Transcript | ListenError]:
    """Yield interim and final transcripts until the caller stops the iterator."""
    key = api_key()
    if key is None:
        yield ListenError("DEEPGRAM_API_KEY is missing")
        return

    loop = asyncio.get_running_loop()
    audio: asyncio.Queue[bytes] = asyncio.Queue()

    def on_audio(indata, frames, time, status) -> None:
        loop.call_soon_threadsafe(audio.put_nowait, bytes(indata))

    # The mic starts before the socket so words said while it connects are
    # queued and sent, not lost.
    stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        callback=on_audio,
    )
    headers = {"Authorization": f"Token {key}"}
    with stream:
        try:
            socket = await websockets.connect(LISTEN_URL, additional_headers=headers)
        except Exception as error:
            yield ListenError(str(error))
            return
        async with socket:
            send_task = asyncio.create_task(_send_audio(socket, audio))
            try:
                async for event in _read_transcripts(socket):
                    yield event
            finally:
                send_task.cancel()
                await asyncio.gather(send_task, return_exceptions=True)


async def _send_audio(socket, audio: asyncio.Queue[bytes]) -> None:
    while True:
        chunk = await audio.get()
        await socket.send(chunk)


async def _read_transcripts(socket) -> AsyncIterator[Transcript | ListenError]:
    """Deepgram finalizes a sentence in several `is_final` segments and marks the
    last one `speech_final`. Segments are joined so a pause mid-command does not
    cut it short; only the end of the utterance yields a final transcript."""
    spoken: list[str] = []
    async for raw in socket:
        if isinstance(raw, bytes):
            continue
        message = json.loads(raw)
        kind = message.get("type")
        if kind == "Error":
            yield ListenError(message.get("description") or message.get("message") or "deepgram error")
            return
        if kind != "Results":
            continue
        alternatives = message.get("channel", {}).get("alternatives") or []
        text = (alternatives[0].get("transcript") or "").strip() if alternatives else ""
        if message.get("is_final"):
            if text:
                spoken.append(text)
            if message.get("speech_final") and spoken:
                yield Transcript(" ".join(spoken), True)
                spoken = []
            elif spoken:
                yield Transcript(" ".join(spoken), False)
        elif text:
            yield Transcript(" ".join([*spoken, text]), False)
    if spoken:
        yield Transcript(" ".join(spoken), True)


def main() -> None:
    async def run() -> None:
        async for event in listen():
            if isinstance(event, ListenError):
                print(f"error: {event.message}")
                return
            mark = "final" if event.final else "live"
            print(f"{mark}: {event.text}", flush=True)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
