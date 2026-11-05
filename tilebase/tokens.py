"""Collectible tokens: the points a level pays and the HUD shows.

Picking one up removes it from the map and grants a point on the credit
ledger. Spending that balance on a voice edit comes later. A token is drawn
as the X Money glyph (`assets/icons/xmoney.svg`, from x.com's own icon set).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tilebase.art import icon_image
from tilebase.credits import Ledger, grant
from tilebase.geom import Rect
from tilebase.tiles import World, cells_overlapping, put_cell

TOKEN_MARK = "token"
# The title menu draws on a 320x180 canvas; the play view is 640x360.
HUD_PX = 2
HUD_MARGIN = 8
POP_TIME = 0.7
ROLL_RATE = 10.0
ROLL_MIN = 6.0
# The +N that floats off the sign, and the digits while they flash.
GOLD = (250, 204, 72)
EMBER = (150, 70, 10)

_signs: dict[tuple[str, bool], object] = {}


def draw_token(screen: object, rect: Rect) -> None:
    """The X Money glyph in the cell. It bobs so it reads as an item, not a tile."""
    import pygame

    bob = math.sin(pygame.time.get_ticks() / 1000.0 * 3.2) * 2.5
    _paint_money(
        screen,
        rect.x + rect.w / 2,
        rect.y + rect.h / 2 + bob,
        min(rect.w, rect.h) * 0.72,
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


@dataclass(frozen=True)
class CounterLook:
    """What the HUD counter shows: a rolling number and the last pickup's pop."""

    target: int = 0
    shown: float = 0.0
    pop: float = 0.0
    gain: int = 0


def counter_step(look: CounterLook, balance: int | None, dt: float) -> CounterLook:
    """Roll the shown number toward the balance; a gain restarts the pop."""
    if balance is None:
        return look
    pop = max(0.0, look.pop - dt)
    gain = look.gain
    if balance > look.target:
        gain = balance - look.target + (gain if pop > 0 else 0)
        pop = POP_TIME
    gap = balance - look.shown
    step = max(ROLL_MIN, abs(gap) * ROLL_RATE) * dt
    shown = balance if abs(gap) <= step else look.shown + math.copysign(step, gap)
    return CounterLook(target=balance, shown=shown, pop=pop, gain=gain if pop > 0 else 0)


def draw_balance(
    screen: object, balance: int | None, view_w: int, look: CounterLook | None = None
) -> None:
    """Stone sign in the top-right corner, drawn like the title menu's buttons.

    A brass badge carries the X Money glyph; the count rolls up on a pickup
    while the sign hops and a `+N` floats off it. `None` is the unlimited ledger.
    """
    look = look or CounterLook(target=balance or 0, shown=float(balance or 0))
    count = "INF" if balance is None else str(round(look.shown))
    t = 1.0 - look.pop / POP_TIME if look.pop > 0 else 1.0
    flash = look.pop > 0 and t < 0.35
    sign = _sign_image(count, flash)
    lift = round(math.sin(t * math.pi) * 3) if look.pop > 0 else 0
    x = view_w - HUD_MARGIN - sign.get_width()
    y = HUD_MARGIN - lift * HUD_PX
    screen.blit(sign, (x, y))
    if look.pop > 0 and look.gain > 0:
        from tilebase.title import INK, pixel_text

        label = f"+{look.gain}"
        face = pixel_text(label, GOLD, HUD_PX * 2)
        rim = pixel_text(label, INK, HUD_PX * 2)
        lx = x - face.get_width() - 6 * HUD_PX - round(t * 6) * HUD_PX
        ly = y + (sign.get_height() - face.get_height()) // 2 - round(t * 4) * HUD_PX
        alpha = 255 if t < 0.6 else round(255 * (1.0 - t) / 0.4)
        rim.set_alpha(alpha)
        face.set_alpha(alpha)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
            screen.blit(rim, (lx + dx * HUD_PX, ly + dy * HUD_PX))
        screen.blit(face, (lx, ly))


def _sign_image(count: str, flash: bool) -> object:
    """The stone sign with badge and number, cached per text and flash state."""
    key = (count, flash)
    if key in _signs:
        return _signs[key]
    import pygame

    from tilebase.art import source_image
    from tilebase.title import INK, PAPER, brass_platform, pixel_text, stone_sign

    digits = pixel_text(count, EMBER if flash else INK, 2)
    caption = pixel_text("TOKENS", INK, 1)
    badge = 24
    pad = 3
    gap = 5
    # Room for two digits so the sign does not twitch on the first few pickups.
    text_w = max(digits.get_width(), caption.get_width(), pixel_text("00", INK, 2).get_width())
    w = pad + badge + gap + text_w + pad + 4
    h = badge + pad * 2 + 2
    canvas = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    stone_sign(canvas, Rect(0, 0, w, h), source_image("tiles", "solid.png"))
    glyph = icon_image("xmoney", 18, PAPER if flash else INK)
    brass_platform(canvas, Rect(pad, pad + 1, badge, badge), source_image("tiles", "platform.png"), glyph)
    tx = pad + badge + gap
    canvas.blit(caption, (tx, pad + 1))
    canvas.blit(digits, (tx, pad + 1 + caption.get_height() + 2))
    image = pygame.transform.scale(canvas, ((w + 2) * HUD_PX, (h + 2) * HUD_PX))
    _signs[key] = image
    return image


def _paint_money(screen: object, cx: float, cy: float, size: float) -> None:
    """The glyph centred on (cx, cy), white over a dark rim so it reads on any art."""
    px = max(6, round(size))
    rim = icon_image("xmoney", px, (10, 8, 20))
    face = icon_image("xmoney", px, (255, 255, 255))
    left = round(cx - px / 2)
    top = round(cy - px / 2)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
        screen.blit(rim, (left + dx, top + dy))
    screen.blit(face, (left, top))
