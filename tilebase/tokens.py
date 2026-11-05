"""Collectible tokens: the points a level pays and the HUD shows.

Picking one up removes it from the map and grants a point on the credit
ledger. Spending that balance on a voice edit comes later.
"""

from __future__ import annotations

import math

from tilebase.credits import Ledger, grant
from tilebase.geom import Rect
from tilebase.tiles import World, cells_overlapping, put_cell

TOKEN_MARK = "token"

_fonts: dict[int, object | None] = {}


def draw_token(screen: object, rect: Rect) -> None:
    """A coin in the cell. It bobs so a pickup reads as an item, not a tile."""
    import pygame

    bob = math.sin(pygame.time.get_ticks() / 1000.0 * 3.2) * 2.5
    _paint_coin(
        screen,
        rect.x + rect.w / 2,
        rect.y + rect.h / 2 + bob,
        min(rect.w, rect.h) * 0.30,
    )


def collect(
    world: World, rect: Rect, ledger: Ledger, *, empty_id: str = "empty"
) -> tuple[World, Ledger, int]:
    """Grant one token per overlapping pickup and clear those cells."""
    gained = 0
    current = world
    for cell in cells_overlapping(world, rect):
        if TOKEN_MARK not in cell.marks:
            continue
        updated = put_cell(current, cell.col, cell.row, empty_id)
        if not isinstance(updated, World):
            continue
        current = updated
        gained += 1
    if gained == 0:
        return world, ledger, 0
    return current, grant(ledger, gained, reason="collect"), gained


def draw_balance(screen: object, balance: int | None, view_w: int) -> None:
    """Token counter in the top-right corner. `None` is the unlimited ledger."""
    import pygame

    count_font = _font(28)
    word_font = _font(18)
    count = "∞" if balance is None else str(balance)
    count_img = count_font.render(count, True, (255, 246, 214)) if count_font else None
    word_img = word_font.render("tokens", True, (236, 214, 150)) if word_font else None
    count_w = count_img.get_width() if count_img is not None else 14
    word_w = word_img.get_width() if word_img is not None else 0
    radius = 7
    pad_x = 10
    gap = 6
    height = 30
    width = pad_x + radius * 2 + gap + word_w + (gap if word_w else 0) + count_w + pad_x
    margin = 8
    x = view_w - margin - width
    y = margin
    panel = pygame.Surface((width, height), pygame.SRCALPHA)
    panel.fill((12, 10, 22, 180))
    screen.blit(panel, (x, y))
    pygame.draw.rect(
        screen,
        (214, 168, 64),
        pygame.Rect(x, y, width, height),
        width=1,
        border_radius=8,
    )
    cx = x + pad_x + radius
    cy = y + height // 2
    _paint_coin(screen, cx, cy, radius)
    cursor = cx + radius + gap
    if word_img is not None:
        screen.blit(word_img, (cursor, y + (height - word_img.get_height()) // 2))
        cursor += word_w + gap
    if count_img is not None:
        screen.blit(count_img, (cursor, y + (height - count_img.get_height()) // 2))


def _paint_coin(screen: object, cx: float, cy: float, radius: float) -> None:
    import pygame

    r = max(2, round(radius))
    center = (round(cx), round(cy))
    pygame.draw.circle(screen, (92, 58, 12), center, r + 2)
    pygame.draw.circle(screen, (242, 188, 52), center, r)
    pygame.draw.circle(
        screen,
        (255, 232, 160),
        (round(cx - r * 0.28), round(cy - r * 0.32)),
        max(1, r // 3),
    )


def _font(size: int) -> object | None:
    if size not in _fonts:
        import pygame

        try:
            _fonts[size] = pygame.font.Font(None, size)
        except (NotImplementedError, pygame.error):
            _fonts[size] = None
    return _fonts[size]
