"""Nikolas's painted art: tiles, the backdrop and the Grok Bot ball.

Images load once, on first use, and are scaled down from the source PNGs
(512px tiles, 256px player frames, 1280x720 backdrop) to game size. Choosing
what to draw (`pose_for`, `backdrop_offset`) is pure; only the draw calls
touch pygame.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Protocol

from tilebase.geom import Rect, Size, Vec2

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TILE_NAMES = ("solid", "block", "bridge", "platform", "door", "exit", "spike")
POSES = ("idle", "jump", "climb")

# The ball fills ~225 of the 256 source pixels; this keeps it 26px across,
# the same size as the old blob and the radius `blob.update_look` rolls by.
PLAYER_SIZE = 30
# Rotation and squash work on a mid-size copy so edges stay smooth.
PLAYER_HI = PLAYER_SIZE * 4
# Dash spent: tint the black ball toward blue, as the blob did.
SPENT_TINT = (34, 58, 112)
# The backdrop covers this much more than the view so it can drift (parallax).
BACKDROP_OVERSCAN = 1.25

_cache: dict[tuple, object] = {}


class PlayerLike(Protocol):
    @property
    def on_ground(self) -> bool: ...
    @property
    def wall_sliding(self) -> bool: ...
    @property
    def wall_dir(self) -> int: ...
    @property
    def facing(self) -> int: ...


def pose_for(player: PlayerLike) -> tuple[str, bool]:
    """Which frame to draw, and whether to mirror it (art faces right)."""
    if player.wall_sliding:
        return "climb", player.wall_dir < 0
    if not player.on_ground:
        return "jump", player.facing < 0
    return "idle", player.facing < 0


def backdrop_offset(cam: Vec2, world: Size, view: Size, art: Size) -> Vec2:
    """Top-left of the backdrop on screen. It slides less than the camera."""

    def axis(c: float, w: float, v: float, a: float) -> float:
        span = w - v
        t = 0.5 if span <= 0 else min(max((c - v / 2) / span, 0.0), 1.0)
        return -(a - v) * t

    return Vec2(axis(cam.x, world.w, view.w, art.w), axis(cam.y, world.h, view.h, art.h))


def _load(path: Path) -> object:
    import pygame

    if pygame.image.get_extended():
        image = pygame.image.load(str(path))
        if pygame.display.get_surface() is not None:
            image = image.convert_alpha()
        return image
    from tilebase.png import load_png

    return load_png(path)


def _cached(key: tuple, make: Callable[[], object]) -> object:
    if key not in _cache:
        _cache[key] = make()
    return _cache[key]


def tile_image(name: str, size: int) -> object:
    import pygame

    return _cached(
        ("tile", name, size),
        lambda: pygame.transform.smoothscale(_load(ASSETS / "tiles" / f"{name}.png"), (size, size)),
    )


def icon_image(name: str, size: int, color: tuple[int, int, int]) -> object:
    """A white icon from `assets/icons`, scaled to `size` and tinted `color`."""
    import pygame

    def make() -> object:
        image = pygame.transform.smoothscale(_load(ASSETS / "icons" / f"{name}.png"), (size, size))
        image.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return image

    return _cached(("icon", name, size, color), make)


def tile_drawer(name: str) -> Callable[[object, Rect], None]:
    """A `define(draw=...)` function that paints one tile from the art."""

    def draw(screen: object, rect: Rect) -> None:
        size = round(rect.w)
        screen.blit(tile_image(name, size), (round(rect.x), round(rect.y)))

    return draw


def backdrop_image(view: Size) -> object:
    import pygame

    w = round(view.w * BACKDROP_OVERSCAN)
    h = round(view.h * BACKDROP_OVERSCAN)
    return _cached(
        ("backdrop", w, h),
        lambda: pygame.transform.smoothscale(_load(ASSETS / "bg.png"), (w, h)),
    )


def draw_backdrop(screen: object, cam: Vec2, world: Size, view: Size) -> None:
    image = backdrop_image(view)
    art = Size(image.get_width(), image.get_height())
    at = backdrop_offset(cam, world, view, art)
    screen.blit(image, (round(at.x), round(at.y)))


def _player_image(pose: str, mirror: bool, spent: bool) -> object:
    import pygame

    def make() -> object:
        image = pygame.transform.smoothscale(
            _load(ASSETS / "player" / f"{pose}.png"), (PLAYER_HI, PLAYER_HI)
        )
        if mirror:
            image = pygame.transform.flip(image, True, False)
        if spent:
            image = image.copy()
            image.fill(SPENT_TINT, special_flags=pygame.BLEND_RGB_ADD)
        return image

    return _cached(("player", pose, mirror, spent), make)


def draw_player(
    screen: object,
    center: Vec2,
    player: PlayerLike,
    look: object,
    *,
    dashes_left: int,
) -> None:
    """Draw the ball spun by `look.roll` and squashed by the blob springs."""
    import pygame

    pose, mirror = pose_for(player)
    image = _player_image(pose, mirror, dashes_left <= 0)
    image = pygame.transform.rotozoom(image, -math.degrees(look.roll), 1.0)

    k = PLAYER_SIZE / PLAYER_HI
    sx, sy = look.sx, look.sy
    w = max(1, round(image.get_width() * k * sx))
    h = max(1, round(image.get_height() * k * sy))
    image = pygame.transform.smoothscale(image, (w, h))
    if look.angle:
        image = pygame.transform.rotozoom(image, -math.degrees(look.angle), 1.0)

    # Keep the feet planted while squashed, and lean into walls.
    r = PLAYER_SIZE * 0.43
    x = center.x + look.lean
    y = center.y + (1.0 - sy) * r
    screen.blit(image, image.get_rect(center=(round(x), round(y))))
