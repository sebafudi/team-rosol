"""Title screen. `ascii` prints the painted hills as characters; `paper` dithers."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from pathlib import Path

from tilebase.geom import Rect, Size

INK = (28, 24, 22)
PAPER = (236, 224, 196)
MOSS = (100, 104, 53)
SHADOW = (62, 44, 28)
# Same camera the game frames, so the menu shares its pixel grid.
FRAME = Size(320, 180)
VARIANTS = ("ascii", "paper")
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
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "+": ("00100", "00100", "11111", "00100", "00100", "00000", "00000"),
    "*": ("10101", "01110", "11111", "01110", "10101", "00000", "00000"),
    "#": ("01010", "11111", "01010", "11111", "01010", "11111", "01010"),
    "%": ("11000", "11001", "00010", "00100", "01000", "10011", "00011"),
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110"),
}
# Sparse in the sky, dense on the hills. Each mark is a darker shade of that pixel.
_RAMP = " .:-=+*#%@"
_PROMPT = "> YOU JUMP"


@dataclass(frozen=True)
class TitleLayout:
    wordmark: Rect
    subtitle: Rect
    mascot: Rect
    button: Rect


@dataclass(frozen=True)
class AsciiLayout:
    plate: Rect
    wordmark: Rect
    subtitle: Rect
    mascot: Rect
    button: Rect
    hint: Rect


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


def ascii_layout(width: int, height: int, time: float) -> AsciiLayout:
    """Stone sign up top, the bot standing on a Play platform."""
    word_scale = 2 if width >= 280 else 1
    word_w, word_h = 68 * word_scale, 16 * word_scale
    sub_w = len("THE GAP") * 6 - 1
    plate_w = word_w + 16
    plate_h = 6 + word_h + 3 + 7 + 5
    plate = Rect((width - plate_w) / 2, max(8, height * 0.08), plate_w, plate_h)
    word = Rect(plate.x + (plate_w - word_w) / 2, plate.y + 5, word_w, word_h)
    subtitle = Rect((width - sub_w) / 2, word.y + word_h + 3, sub_w, 7)
    button_w = 112 if width >= 280 else 80
    button_h = 20 if width >= 280 else 16
    button = Rect((width - button_w) / 2, height - button_h - 22, button_w, button_h)
    mascot_size = 16 * (3 if width >= 280 else 2)
    bob = round(math.sin(time * 5.0) * 3)
    mascot = Rect(
        button.x + button.w / 2 - mascot_size / 2,
        button.y - mascot_size + bob,
        mascot_size,
        mascot_size,
    )
    hint_w = len(_PROMPT) * 6 - 1
    hint = Rect((width - hint_w) / 2, button.y + button_h + 6, hint_w, 7)
    return AsciiLayout(
        plate=plate,
        wordmark=word,
        subtitle=subtitle,
        mascot=mascot,
        button=button,
        hint=hint,
    )


async def show(screen, *, variant: str = "ascii", max_frames: int | None = None) -> str:
    if variant not in VARIANTS:
        variant = "ascii"
    if variant == "paper":
        return await _show_paper(screen, max_frames=max_frames)
    return await _show_ascii(screen, max_frames=max_frames)


async def _show_paper(screen, *, max_frames: int | None = None) -> str:
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


async def _show_ascii(screen, *, max_frames: int | None = None) -> str:
    import pygame

    from tilebase.view import fit_display

    art = _load_art()
    if art is None:
        return "quit"
    width, height = screen.get_size()
    fitted = fit_display(Size(width, height), FRAME)
    canvas = pygame.Surface((fitted.camera.w, fitted.camera.h)).convert()
    frames = _ascii_frames((fitted.camera.w, fitted.camera.h), art["bg"])
    big = fitted.camera.w >= 280
    label = _text("PLAY", INK, 2 if big else 1)
    subtitle = _text("THE GAP", INK, 1)
    hint_on = _text(_PROMPT, INK, 1)
    hint_off = _text(" " + _PROMPT[1:], INK, 1)
    clock = pygame.time.Clock()
    time = 0.0
    drawn = 0
    while max_frames is None or drawn < max_frames:
        layout = ascii_layout(fitted.camera.w, fitted.camera.h, time)
        choice = None
        for event in pygame.event.get():
            choice = _action(event, _screen_rect(layout.button, fitted)) or choice
        if choice is not None:
            return choice
        canvas.blit(frames[int(time * 6) % 4], (0, 0))
        _sign(canvas, layout.plate, art["solid"])
        _blit_nearest(canvas, art["wordmark"], layout.wordmark)
        canvas.blit(subtitle, (layout.subtitle.x, layout.subtitle.y))
        _platform(canvas, layout.button, art["platform"], label)
        _blit_nearest(canvas, art["mascot"], layout.mascot)
        hint = hint_on if int(time * 2) % 2 == 0 else hint_off
        canvas.blit(hint, (layout.hint.x, layout.hint.y))
        _present(screen, canvas, fitted)
        pygame.display.flip()
        time += clock.tick(60) / 1000.0
        drawn += 1
        await asyncio.sleep(0)
    return "quit"


def _load_art():
    from tilebase.png import PngError, load_png

    root = assets_dir().parent
    paths = {
        "wordmark": assets_dir() / "wordmark.png",
        "mascot": assets_dir() / "mascot.png",
        "bg": root / "bg.png",
        "solid": root / "tiles" / "solid.png",
        "platform": root / "tiles" / "platform.png",
    }
    loaded = {}
    for name, path in paths.items():
        image = load_png(path)
        if isinstance(image, PngError):
            return None
        loaded[name] = image
    return loaded


def _ascii_frames(size: tuple[int, int], bg):
    """One character per pixel of the painting. The sign and the bot stay clear."""
    import pygame

    width, height = size
    cell_w, cell_h = 8, 9
    cols = max(1, width // cell_w)
    rows = max(1, height // cell_h)
    origin_x = (width - cols * cell_w) // 2
    origin_y = (height - rows * cell_h) // 2
    small = pygame.transform.smoothscale(bg, (cols, rows))
    blocks = pygame.transform.scale(small, (cols * cell_w, rows * cell_h))
    quiet = _quiet(width, height)
    frames = []
    for phase in range(4):
        frame = pygame.Surface((width, height))
        edge = small.get_at((0, rows - 1))
        frame.fill((edge.r, edge.g, edge.b))
        frame.blit(blocks, (origin_x, origin_y))
        for y in range(rows):
            for x in range(cols):
                px = origin_x + x * cell_w
                py = origin_y + y * cell_h
                if _covered(px, py, cell_w, cell_h, quiet):
                    continue
                color = small.get_at((x, y))
                glyph, mark = _cell_glyph(color, x, y, phase)
                if glyph == " ":
                    continue
                _stamp(frame, glyph, px + 1, py + 1, mark)
        frames.append(frame)
    return tuple(frames)


def _quiet(width: int, height: int) -> tuple[Rect, ...]:
    layout = ascii_layout(width, height, 0.0)
    return (
        layout.plate,
        layout.button,
        Rect(layout.hint.x - 8, layout.hint.y - 6, layout.hint.w + 16, layout.hint.h + 10),
        Rect(layout.mascot.x - 2, layout.mascot.y - 4, layout.mascot.w + 4, layout.mascot.h + 8),
    )


def _covered(x: int, y: int, w: int, h: int, rects: tuple[Rect, ...]) -> bool:
    for rect in rects:
        if x + w > rect.x and x < rect.x + rect.w and y + h > rect.y and y < rect.y + rect.h:
            return True
    return False


def _cell_glyph(color, x: int, y: int, phase: int) -> tuple[str, tuple[int, int, int]]:
    # The sun is a warm hole in the sky. Mark it with a spark instead of a dot.
    if color.r > 248 and color.g > 220 and color.r > color.b + 25:
        return "*", (color.r * 3 // 5, color.g * 2 // 5, color.b // 3)
    return _RAMP[_ramp_index(color.r, color.g, color.b, x, y, phase)], _mark(color)


def _ramp_index(red: int, green: int, blue: int, x: int, y: int, phase: int) -> int:
    # The painting is all bright. Stretch the hills-to-sky range across the ramp.
    luma = (red * 3 + green * 4 + blue) // 8
    span = (luma - 130) * 255 // 120
    if span < 0:
        span = 0
    if span > 255:
        span = 255
    last = len(_RAMP) - 1
    base = (255 - span) * last // 255
    jitter = ((_BAYER[((y & 3) << 2) + (x & 3)] + phase * 4) & 15) - 8
    if jitter > 3:
        base += 1
    elif jitter < -3:
        base -= 1
    if base < 0:
        return 0
    if base > last:
        return last
    return base


def _mark(color) -> tuple[int, int, int]:
    return (
        max(48, color.r * 9 // 20),
        max(40, color.g * 8 // 20),
        max(32, color.b * 7 // 20),
    )


def _stamp(surface, character: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    for row, bits in enumerate(_GLYPHS[character]):
        for col, bit in enumerate(bits):
            if bit == "1":
                surface.set_at((x + col, y + row), color)


def _sign(surface, rect: Rect, tile) -> None:
    """One stone slab, not a grid of tiles, so the wordmark's eyes read as stone."""
    import pygame

    pygame.draw.rect(surface, SHADOW, _box(Rect(rect.x + 2, rect.y + 2, rect.w, rect.h)))
    _blit_chunk(surface, _crop(tile, 64), rect, 4)
    x, y, w, h = _box(rect)
    pygame.draw.rect(surface, (232, 214, 176), (x, y, w, 1))
    pygame.draw.rect(surface, (232, 214, 176), (x, y, 1, h))
    pygame.draw.rect(surface, (120, 96, 64), (x, y + h - 1, w, 1))
    pygame.draw.rect(surface, (120, 96, 64), (x + w - 1, y, 1, h))
    pygame.draw.rect(surface, MOSS, (x + 1, y + h - 3, w - 2, 2))
    pygame.draw.rect(surface, INK, (x, y, w, h), 1)


def _platform(surface, rect: Rect, tile, label) -> None:
    """The Play control is a single brass platform: moss lip, gold face."""
    import pygame

    pygame.draw.rect(surface, SHADOW, _box(Rect(rect.x + 2, rect.y + 2, rect.w, rect.h)))
    x, y, w, h = _box(rect)
    _blit_chunk(surface, _crop(tile, 140), rect, 4)
    lip = tile.subsurface((80, 20, tile.get_width() - 160, 18))
    surface.blit(pygame.transform.scale(lip, (w, 4)), (x, y))
    pygame.draw.rect(surface, (48, 34, 6), (x, y + h - 2, w, 2))
    pygame.draw.rect(surface, INK, (x, y, w, h), 1)
    surface.blit(
        label,
        (
            rect.x + (rect.w - label.get_width()) / 2,
            rect.y + (rect.h - label.get_height()) / 2,
        ),
    )


def _crop(image, inset: int):
    width, height = image.get_size()
    return image.subsurface((inset, inset, width - 2 * inset, height - 2 * inset))


def _blit_chunk(surface, image, rect: Rect, pixels: int) -> None:
    import pygame

    width, height = max(1, int(rect.w) // pixels), max(1, int(rect.h) // pixels)
    tiny = pygame.transform.scale(image, (width, height))
    surface.blit(pygame.transform.scale(tiny, (int(rect.w), int(rect.h))), (int(rect.x), int(rect.y)))


def _screen_rect(rect: Rect, fitted) -> Rect:
    scale = fitted.scale
    return Rect(
        fitted.x + rect.x * scale,
        fitted.y + rect.y * scale,
        rect.w * scale,
        rect.h * scale,
    )


def _present(screen, canvas, fitted) -> None:
    import pygame

    screen.fill(INK)
    size = (fitted.camera.w * fitted.scale, fitted.camera.h * fitted.scale)
    screen.blit(pygame.transform.scale(canvas, size), (fitted.x, fitted.y))


def _box(rect: Rect):
    return (int(rect.x), int(rect.y), int(rect.w), int(rect.h))


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
