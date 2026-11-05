"""Time a recorded voice command from the end of speech to a placed box.

    python -m scripts.bench_voice [wav] [runs]
    BENCH_MODEL_ONLY=1 python -m scripts.bench_voice   # skip speech, time ask() alone

The WAV (16 kHz mono int16) is streamed to Deepgram at real-time speed, the
way the microphone would send it, then trailing silence keeps flowing until
the transcript settles. The game's own level render and `ask()` run after.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
import wave
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import websockets  # noqa: E402

from tilebase import agent, speech  # noqa: E402

CHUNK_SECONDS = 0.1
SILENCE_LIMIT = 4.0


def _speech_end(frames: bytes, rate: int) -> float:
    """Seconds into the clip where the last loud 20 ms window ends."""
    window = rate // 50
    last = 0
    for start in range(0, len(frames) // 2, window):
        chunk = frames[start * 2 : (start + window) * 2]
        samples = memoryview(chunk).cast("h")
        if samples and max(abs(s) for s in samples) > 800:
            last = start + window
    return last / rate


def _level_png() -> bytes:
    import pygame

    from tilebase import blob, player
    from tilebase.box import level_surface, open_level
    from tilebase.geom import Vec2
    from tilebase.play import _frame_png

    pygame.init()
    pygame.display.set_mode((1, 1))
    level = open_level()
    p = player.spawn(level.spawn.x, level.spawn.y)
    rect = p.body.rect
    center = Vec2(rect.x + rect.w / 2, rect.y + rect.h / 2)
    sheet = level_surface(level.world, level.entities, center, p, blob.rest(), p.dashes_left)
    return _frame_png(sheet)


async def _stt(frames: bytes, rate: int) -> dict:
    """Stream the clip in real time. Return the transcript and phase times."""
    key = speech.api_key()
    began = time.perf_counter()
    socket = await websockets.connect(
        speech.LISTEN_URL, additional_headers={"Authorization": f"Token {key}"}
    )
    connected = time.perf_counter()
    step = int(rate * CHUNK_SECONDS) * 2
    silence = b"\0" * step
    spoken = _speech_end(frames, rate)
    out: dict = {"connect": connected - began}

    async def send() -> None:
        start = time.perf_counter()
        sent = 0.0
        for at in range(0, len(frames), step):
            await socket.send(frames[at : at + step])
            sent += CHUNK_SECONDS
            await asyncio.sleep(max(0.0, start + sent - time.perf_counter()))
        while sent < len(frames) / 2 / rate + SILENCE_LIMIT:
            await socket.send(silence)
            sent += CHUNK_SECONDS
            await asyncio.sleep(max(0.0, start + sent - time.perf_counter()))

    async with socket:
        stream_start = time.perf_counter()
        sender = asyncio.create_task(send())
        try:
            async for event in speech._read_transcripts(socket):
                if isinstance(event, speech.ListenError):
                    raise RuntimeError(event.message)
                if event.final:
                    out["text"] = event.text
                    out["final_at"] = time.perf_counter()
                    break
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
    out["speech_end_at"] = stream_start + spoken
    return out


def _in_gap(result: object) -> bool:
    """The box hangs over the floor gap (cols 4-11) with air on both sides."""
    return isinstance(result, agent.Placed) and 5 <= result.col <= 9 and result.row in (6, 7)


def run_model(text: str, png: bytes) -> dict:
    asked = time.perf_counter()
    result = agent.ask(text, png)
    took = time.perf_counter() - asked
    return {"text": text, "result": repr(result), "ok": _in_gap(result), "model": took, "total_after_speech": took}


def run_once(frames: bytes, rate: int, png: bytes) -> dict:
    heard = asyncio.run(_stt(frames, rate))
    asked = time.perf_counter()
    result = agent.ask(heard["text"], png)
    placed = time.perf_counter()
    return {
        "text": heard["text"],
        "result": repr(result),
        "ok": _in_gap(result),
        "connect": heard["connect"],
        "stt_after_speech": heard["final_at"] - heard["speech_end_at"],
        "model": placed - asked,
        "total_after_speech": heard["final_at"] - heard["speech_end_at"] + placed - asked,
    }


def main() -> None:
    clip = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "bench" / "place_box_between_gaps.wav"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    with wave.open(str(clip)) as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    png = _level_png()
    chosen = agent.provider()
    model_only = bool(os.environ.get("BENCH_MODEL_ONLY"))
    agent.warm()
    print(f"provider={chosen.host} model={chosen.model} png={len(png)} bytes clip={clip.name}", flush=True)
    rows = []
    for n in range(runs):
        row = run_model("Place the box between the two gaps.", png) if model_only else run_once(frames, rate, png)
        rows.append(row)
        print(json.dumps({"run": n, **{k: round(v, 3) if isinstance(v, float) else v for k, v in row.items()}}), flush=True)
    print(f"{'correct':>20}: {sum(r['ok'] for r in rows)}/{len(rows)}")
    for name in ("connect", "stt_after_speech", "model", "total_after_speech"):
        if name not in rows[0]:
            continue
        values = [r[name] for r in rows]
        print(f"{name:>20}: median {statistics.median(values):.3f}s  min {min(values):.3f}s  max {max(values):.3f}s")


if __name__ == "__main__":
    main()
