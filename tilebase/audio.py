"""Synthesized music and effects for the movement sandbox.

Clips are built when playback starts, so the repo has no audio files and
nothing to license. Jump, wall jump, dash, land, ceiling bonk, and death are
short. The music is a four-bar loop in F major.

This pygame build ships without the mixer module, so playback queues PCM
straight into SDL2, which pygame already links. If the device will not open,
every call does nothing and the game keeps running.
"""

from __future__ import annotations

import array
import ctypes
import math
import sys
import threading
from collections.abc import Set
from dataclasses import dataclass

RATE = 22050
BPM = 100
EIGHTH = 60.0 / BPM / 2.0

_SEMITONE = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "Bb": 10,
}

# Eighth notes. "." is a rest. Four bars, then the buffer loops.
_LEAD = (
    "C5 A4 F4 A4 C5 . D5 C5",
    "D5 C5 A4 F4 A4 G4 . .",
    "Bb4 D5 F5 D5 C5 Bb4 A4 .",
    "E5 D5 C5 Bb4 A4 G4 F4 .",
)
# Quarter notes, the root and the color of each bar: F, Dm, Bb, C.
_BASS = (
    "F2 C3 A3 C3",
    "D2 A2 F3 A2",
    "Bb2 F3 D3 F3",
    "C2 G2 E3 G2",
)
_CHORDS = (
    ("F3", "A3", "C4"),
    ("D3", "F3", "A3"),
    ("Bb2", "D3", "F3"),
    ("C3", "E3", "G3"),
)


_SDL_INIT_AUDIO = 0x00000010
_S16 = 0x8010 if sys.byteorder == "little" else 0x9010
_ALLOW_RATE_AND_CHANNELS = 0x01 | 0x04


class _AudioSpec(ctypes.Structure):
    _fields_ = [
        ("freq", ctypes.c_int),
        ("format", ctypes.c_uint16),
        ("channels", ctypes.c_uint8),
        ("silence", ctypes.c_uint8),
        ("samples", ctypes.c_uint16),
        ("padding", ctypes.c_uint16),
        ("size", ctypes.c_uint32),
        ("callback", ctypes.c_void_p),
        ("userdata", ctypes.c_void_p),
    ]


@dataclass
class _Voice:
    pcm: array.array
    gain: float
    loop: bool
    pos: float = 0.0
    paused: bool = False
    alive: bool = True


def cues(events: Set[str]) -> tuple[str, ...]:
    """Effect names for one physics tick, in the order they should speak."""
    names = []
    if "jump" in events:
        names.append("jump")
    if "wall_jump" in events:
        names.append("wall_jump")
    if "dash" in events:
        names.append("dash")
    if "bonk" in events:
        names.append("bonk")
    if "land" in events:
        names.append("land")
    return tuple(names)


def land_gain(impact: float) -> float:
    """How loud a landing is. A soft touch stays silent so rolling does not thud."""
    if impact < 200.0:
        return 0.0
    return min(1.0, 0.28 + (impact - 200.0) / 850.0)


def _sdl():
    """SDL2 symbols. pygame has already loaded the library into this process."""
    lib = ctypes.CDLL(None)
    lib.SDL_InitSubSystem.argtypes = [ctypes.c_uint32]
    lib.SDL_InitSubSystem.restype = ctypes.c_int
    lib.SDL_GetError.restype = ctypes.c_char_p
    lib.SDL_OpenAudioDevice.argtypes = [
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.POINTER(_AudioSpec),
        ctypes.POINTER(_AudioSpec),
        ctypes.c_int,
    ]
    lib.SDL_OpenAudioDevice.restype = ctypes.c_uint32
    lib.SDL_PauseAudioDevice.argtypes = [ctypes.c_uint32, ctypes.c_int]
    lib.SDL_QueueAudio.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    lib.SDL_QueueAudio.restype = ctypes.c_int
    lib.SDL_GetQueuedAudioSize.argtypes = [ctypes.c_uint32]
    lib.SDL_GetQueuedAudioSize.restype = ctypes.c_uint32
    lib.SDL_CloseAudioDevice.argtypes = [ctypes.c_uint32]
    if not hasattr(lib, "SDL_OpenAudioDevice"):
        raise OSError("SDL2 audio is not loaded")
    return lib


class Audio:
    """Looping music plus overlapping effects. Safe to call if `start` failed."""

    def __init__(self) -> None:
        self.ready = False
        self.music_on = True
        self._clips: dict[str, array.array] = {}
        self._voices: list[_Voice] = []
        self._music: _Voice | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sdl = None
        self._dev = 0
        self._dev_rate = 44100
        self._channels = 2
        self._frames = 512

    def start(self) -> None:
        import pygame

        if pygame.get_sdl_version() < (2, 0, 4):
            return
        try:
            self._sdl = _sdl()
            if self._sdl.SDL_InitSubSystem(_SDL_INIT_AUDIO) < 0:
                return
            want = _AudioSpec(44100, _S16, 2, 0, 512, 0, 0, None, None)
            got = _AudioSpec()
            dev = self._sdl.SDL_OpenAudioDevice(
                None, 0, ctypes.byref(want), ctypes.byref(got), _ALLOW_RATE_AND_CHANNELS
            )
            if dev == 0 or got.format != _S16 or got.channels not in (1, 2):
                if dev:
                    self._sdl.SDL_CloseAudioDevice(dev)
                return
            self._dev = dev
            self._dev_rate = got.freq
            self._channels = got.channels
            self._frames = got.samples or 512
            self._clips = _effects()
            tune = _Voice(_music(), 0.5, loop=True)
            self._music = tune
            self._voices = [tune]
            self._prime()
            self._thread = threading.Thread(target=self._run, name="audio", daemon=True)
            self._thread.start()
            self._sdl.SDL_PauseAudioDevice(dev, 0)
        except (OSError, AttributeError):
            self._close_device()
            return
        self.ready = True

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=0.5)
        self._close_device()
        self.ready = False

    def play(self, name: str, gain: float = 1.0) -> None:
        if not self.ready or gain <= 0.01:
            return
        pcm = self._clips.get(name)
        if pcm is None:
            return
        voice = _Voice(pcm, min(1.0, gain), loop=False)
        with self._lock:
            self._voices.append(voice)

    def play_events(self, events: Set[str], impact: float) -> None:
        for name in cues(events):
            gain = land_gain(impact) if name == "land" else 0.9
            self.play(name, gain)

    def toggle_music(self) -> None:
        if self._music is None:
            return
        self.music_on = not self.music_on
        self._music.paused = not self.music_on

    def _close_device(self) -> None:
        if self._sdl is not None and self._dev:
            self._sdl.SDL_CloseAudioDevice(self._dev)
            self._dev = 0

    def _prime(self) -> None:
        for _ in range(2):
            self._queue(self._render(self._frames))

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                self._pump()
                self._stop.wait(0.005)
        except Exception:
            return

    def _pump(self) -> None:
        if self._sdl is None or not self._dev:
            return
        frame_bytes = self._frames * self._channels * 2
        queued = self._sdl.SDL_GetQueuedAudioSize(self._dev)
        if queued >= frame_bytes * 2:
            return
        self._queue(self._render(self._frames))

    def _queue(self, buf: array.array) -> None:
        if self._sdl is None or not self._dev or len(buf) == 0:
            return
        self._sdl.SDL_QueueAudio(
            self._dev, ctypes.c_void_p(buf.buffer_info()[0]), len(buf) * 2
        )

    def _render(self, frames: int) -> array.array:
        mix = [0] * frames
        step = RATE / self._dev_rate
        with self._lock:
            for voice in self._voices:
                if not voice.alive or voice.paused:
                    continue
                pcm = voice.pcm
                n = len(pcm)
                pos = voice.pos
                gain = voice.gain
                for i in range(frames):
                    idx = int(pos)
                    while idx >= n:
                        if not voice.loop:
                            voice.alive = False
                            idx = -1
                            break
                        pos -= n
                        idx = int(pos)
                    if idx < 0:
                        break
                    mix[i] += int(pcm[idx] * gain)
                    pos += step
                voice.pos = pos
            self._voices = [voice for voice in self._voices if voice.alive]
        if self._channels == 1:
            return array.array("h", (max(-32767, min(32767, s)) for s in mix))
        stereo = array.array("h")
        for sample in mix:
            sample = max(-32767, min(32767, sample))
            stereo.append(sample)
            stereo.append(sample)
        return stereo


def note_freq(name: str) -> float:
    octave = int(name[-1])
    pitch = name[:-1]
    midi = (octave + 1) * 12 + _SEMITONE[pitch]
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _pcm(samples: list[float]) -> array.array:
    return array.array(
        "h",
        (int(max(-1.0, min(1.0, s)) * 32767.0) for s in samples),
    )


def _noise(n: int, seed: int) -> list[float]:
    out = [0.0] * n
    state = seed & 0x7FFFFFFF or 1
    for i in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        out[i] = (state / 0x7FFFFFFF) * 2.0 - 1.0
    return out


def _lowpass(src: list[float], coeff: float) -> list[float]:
    y = 0.0
    out = [0.0] * len(src)
    for i, x in enumerate(src):
        y += (x - y) * coeff
        out[i] = y
    return out


def _fade_out(buf: list[float], seconds: float) -> None:
    fade = min(len(buf), max(1, int(seconds * RATE)))
    for i in range(fade):
        buf[-fade + i] *= (fade - i) / fade


def _sweep(
    duration: float, f0: float, f1: float, decay: float, amp: float, seed: int
) -> array.array:
    """A soft rising pop: sine sweep plus a tiny noise click at the start."""
    n = max(1, int(RATE * duration))
    noise = _noise(n, seed)
    buf = [0.0] * n
    phase = 0.0
    attack_n = max(1, int(0.005 * RATE))
    for i in range(n):
        u = i / n
        freq = f0 + (f1 - f0) * (1.0 - (1.0 - u) ** 2)
        phase = (phase + freq / RATE) % 1.0
        attack = min(1.0, i / attack_n)
        env = attack * math.exp(-i / (RATE * decay))
        click = noise[i] * math.exp(-i / (RATE * 0.007))
        buf[i] = (math.sin(phase * math.tau) * 0.8 + click * 0.22) * env * amp
    _fade_out(buf, 0.02)
    return _pcm(buf)


def _land() -> array.array:
    n = int(RATE * 0.14)
    noise = _lowpass(_noise(n, 8), 0.15)
    buf = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / RATE
        freq = 130.0 - 70.0 * (i / n)
        phase = (phase + freq / RATE) % 1.0
        env = math.exp(-t / 0.045)
        attack = min(1.0, i / 6.0)
        buf[i] = (math.sin(phase * math.tau) * 0.7 + noise[i] * 0.5) * env * attack
    _fade_out(buf, 0.02)
    return _pcm(buf)


def _dash() -> array.array:
    n = int(RATE * 0.16)
    noise = _noise(n, 5)
    buf = [0.0] * n
    low = 0.0
    phase = 0.0
    for i in range(n):
        u = i / n
        low += (noise[i] - low) * (0.08 + 0.5 * math.sin(math.pi * u))
        phase = (phase + (740.0 - 480.0 * u) / RATE) % 1.0
        tone = math.sin(phase * math.tau) * (1.0 - u)
        env = math.sin(math.pi * u) ** 0.7
        buf[i] = (low * 0.55 + tone * 0.22) * env
    return _pcm(buf)


def _bonk() -> array.array:
    n = int(RATE * 0.08)
    noise = _noise(n, 3)
    buf = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / RATE
        freq = 210.0 * math.exp(-t / 0.025) + 70.0
        phase = (phase + freq / RATE) % 1.0
        env = math.exp(-t / 0.02)
        click = noise[i] * math.exp(-t / 0.008)
        buf[i] = (math.sin(phase * math.tau) * 0.75 + click * 0.18) * env * min(1.0, i / 8.0)
    _fade_out(buf, 0.015)
    return _pcm(buf)


def _death() -> array.array:
    """A splat, a pitch fall, and a second smaller bubble. The jelly pops."""
    n = int(RATE * 0.5)
    noise = _lowpass(_noise(n, 9), 0.22)
    buf = [0.0] * n
    phase = 0.0
    bubble = 0.0
    for i in range(n):
        t = i / RATE
        u = i / n
        wobble = 1.0 + 0.04 * math.sin(math.tau * 12.0 * t)
        freq = (540.0 * (1.0 - u) ** 1.5 + 75.0) * wobble
        phase = (phase + freq / RATE) % 1.0
        tone = math.sin(phase * math.tau) * math.exp(-t / 0.32)
        bub = 0.0
        if t > 0.09:
            bub_f = 280.0 * math.exp(-(t - 0.09) / 0.08) + 90.0
            bubble = (bubble + bub_f / RATE) % 1.0
            bub = math.sin(bubble * math.tau) * math.exp(-(t - 0.09) / 0.1)
        splat = noise[i] * math.exp(-t / 0.04)
        buf[i] = (tone * 0.55 + bub * 0.3 + splat * 0.45) * min(1.0, i / 8.0)
    _fade_out(buf, 0.06)
    return _pcm(buf)


def _effects() -> dict[str, array.array]:
    return {
        "jump": _sweep(0.16, 320.0, 880.0, 0.045, 0.9, 2),
        "wall_jump": _sweep(0.13, 480.0, 1120.0, 0.036, 0.85, 4),
        "land": _land(),
        "dash": _dash(),
        "bonk": _bonk(),
        "death": _death(),
    }


def _add_tone(
    buf: list[float],
    start: float,
    freq: float,
    dur: float,
    amp: float,
    kind: str,
    slide: float = 0.0,
) -> None:
    i0 = int(start * RATE)
    n = int(dur * RATE)
    if n <= 0 or i0 >= len(buf):
        return
    attack = max(1, int(0.012 * RATE))
    release = max(1, int(0.045 * RATE))
    phase = 0.0
    limit = len(buf)
    for i in range(n):
        j = i0 + i
        if j >= limit:
            break
        settled = min(1.0, i / attack)
        inc = freq * (1.0 + slide * (1.0 - settled)) / RATE
        phase += inc
        if phase >= 1.0:
            phase -= 1.0
        if kind == "sine":
            sample = math.sin(phase * math.tau)
        elif kind == "bass":
            sample = -1.0 + 4.0 * phase if phase < 0.5 else 3.0 - 4.0 * phase
        else:
            square = 1.0 if phase < 0.5 else -1.0
            sample = 0.75 * math.sin(phase * math.tau) + 0.25 * square
        env = settled
        if i > n - release:
            env *= (n - i) / release
        buf[j] += sample * env * amp


def _place(
    buf: list[float],
    rows: tuple[str, ...],
    step: float,
    hold: float,
    amp: float,
    kind: str,
    slide: float,
) -> None:
    for bar, row in enumerate(rows):
        origin = bar * 8 * EIGHTH
        for i, token in enumerate(row.split()):
            if token == ".":
                continue
            _add_tone(buf, origin + i * step, note_freq(token), step * hold, amp, kind, slide)


def _music() -> array.array:
    bars = 4
    n = int(bars * 8 * EIGHTH * RATE)
    buf = [0.0] * n
    _place(buf, _LEAD, EIGHTH, 0.88, 0.36, "lead", 0.05)
    _place(buf, _BASS, EIGHTH * 2, 0.94, 0.22, "bass", 0.0)
    bar = 8 * EIGHTH
    for b, chord in enumerate(_CHORDS):
        for name in chord:
            _add_tone(buf, b * bar, note_freq(name), bar * 0.9, 0.04, "sine")
    peak = max(abs(s) for s in buf) or 1.0
    scale = 0.8 / peak if peak > 0.8 else 1.0
    fade = int(0.004 * RATE)
    out = [0.0] * n
    last = n - 1
    for i, sample in enumerate(buf):
        gain = scale
        if i < fade:
            gain *= i / fade
        elif i > last - fade:
            gain *= (last - i) / fade
        out[i] = sample * gain
    return _pcm(out)
