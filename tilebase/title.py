"""Title screen: dithered field, the Grok wordmark, a bouncing mascot, Play."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from pathlib import Path

from tilebase.geom import Rect

INK = (28, 24, 22)
PAPER = (236, 224, 196)
_BAYER = (
    0, 8, 2, 10,
    12, 4, 14, 6,
    3, 11, 1, 9,
    15, 7, 13, 5,
)
_GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


@dataclass(frozen=True)
class TitleLayout:
    wordmark: Rect
    subtitle: Rect
    mascot: Rect
    button: Rect


def assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "title"


def play_layout(width: int, height: int, time: float) -> TitleLayout:
    """Play stays on the screen center. The mascot bobs just left of it."""
    big = width >= 480
    word_scale = 3 if big else 2
    word = Rect((width - 68 * word_scale) // 2, 16 if big else 8, 68 * word_scale, 16 * word_scale)
    sub_scale = 2 if big else 1
    sub_w = (len("THE GAP") * 6 - 1) * sub_scale
    subtitle = Rect((width - sub_w) // 2, word.y + word.h + 6, sub_w, 7 * sub_scale)
    button_w = 140 if big else 76
    button_h = 36 if big else 24
    button = Rect((width - button_w) / 2, (height - button_h) / 2, button_w, button_h)
    mascot_size = 16 * (4 if big else 2)
    bob = round(math.sin(time * 5.0) * (6 if big else 3))
    mascot = Rect(
        button.x + button.w / 2 - mascot_size / 2,
        button.y - mascot_size - (10 if big else 6) + bob,
        mascot_size,
        mascot_size,
    )
    return TitleLayout(wordmark=word, subtitle=subtitle, mascot=mascot, button=button)


async def show(screen, *, max_frames: int | None = None) -> str:
    import pygame

    from tilebase.png import PngError, load_png

    wordmark = load_png(assets_dir() / "wordmark.png")
    mascot = load_png(assets_dir() / "mascot.png")
    if isinstance(wordmark, PngError) or isinstance(mascot, PngError):
        return "quit"
    width, height = screen.get_size()
    frames = tuple(_dither(width, height, phase) for phase in range(4))
    subtitle = _text("THE GAP", INK, 2 if width >= 480 else 1)
    label = _text("PLAY", PAPER, 3 if width >= 480 else 2)
    clock = pygame.time.Clock()
    time = 0.0
    drawn = 0
    while max_frames is None or drawn < max_frames:
        layout = play_layout(width, height, time)
        choice = None
        for event in pygame.event.get():
            choice = _action(event, layout.button) or choice
        if choice is not None:
            return choice
        screen.blit(frames[int(time * 8) % 4], (0, 0))
        _blit_nearest(screen, wordmark, layout.wordmark)
        screen.blit(subtitle, (layout.subtitle.x, layout.subtitle.y))
        _blit_nearest(screen, mascot, layout.mascot)
        _button(screen, layout.button, label)
        pygame.display.flip()
        time += clock.tick(60) / 1000.0
        drawn += 1
        await asyncio.sleep(0)
    return "quit"


def _dither(width: int, height: int, phase: int):
    import pygame

    cell = 4
    low_w = max(1, width // cell)
    low_h = max(1, height // cell)
    buffer = bytearray(low_w * low_h * 3)
    index = 0
    for y in range(low_h):
        for x in range(low_w):
            nx = (x + 0.5) / low_w - 0.5
            ny = (y + 0.5) / low_h - 0.5
            shade = 48 + (nx * nx + ny * ny) * 80
            threshold = ((_BAYER[((y & 3) << 2) + (x & 3)] + phase) & 15) * 16
            color = INK if shade > threshold else PAPER
            buffer[index] = color[0]
            buffer[index + 1] = color[1]
            buffer[index + 2] = color[2]
            index += 3
    payload = bytes(buffer)
    small = pygame.image.frombuffer(payload, (low_w, low_h), "RGB").copy()
    return pygame.transform.scale(small, (width, height))


def _action(event, button: Rect) -> str | None:
    import pygame

    if event.type == pygame.QUIT:
        return "quit"
    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        return "quit"
    if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
        return "play"
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        x, y = event.pos
        if button.x <= x < button.x + button.w and button.y <= y < button.y + button.h:
            return "play"
    return None


def _blit_nearest(screen, image, rect: Rect) -> None:
    import pygame

    scaled = pygame.transform.scale(image, (int(rect.w), int(rect.h)))
    screen.blit(scaled, (int(rect.x), int(rect.y)))


def _button(screen, rect: Rect, label) -> None:
    import pygame

    box = (int(rect.x), int(rect.y), int(rect.w), int(rect.h))
    pygame.draw.rect(screen, INK, box)
    pygame.draw.rect(screen, PAPER, box, 2)
    screen.blit(
        label,
        (
            rect.x + (rect.w - label.get_width()) / 2,
            rect.y + (rect.h - label.get_height()) / 2,
        ),
    )


def _text(message: str, color: tuple[int, int, int], scale: int):
    import pygame

    width = (len(message) * 6 - 1) * scale
    surface = pygame.Surface((width, 7 * scale), pygame.SRCALPHA)
    cursor = 0
    for character in message:
        for row, bits in enumerate(_GLYPHS[character]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    pygame.draw.rect(surface, color, (cursor + col * scale, row * scale, scale, scale))
        cursor += 6 * scale
    return surface
