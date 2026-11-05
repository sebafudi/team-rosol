"""Tile kinds a player can name, and the model can read.

The character is the glyph in the grid sent with a prompt. The marks decide
what the body does:

- blocks: solid on every side (stone, the wooden bridge, a crate, a shut door)
- oneway: jump up through it and land on it (the gold platform)
- hazard: the lower band kills (spikes sit in the bottom of the cell)
- burns: any touch kills (lava fills the whole cell)
- slick: the ground keeps most of your speed (ice)
- bounce: standing on it throws you high (the red spring)
- crumble: it falls away a moment after you stand on it (cracked rock)
- goal: overlap clears the level
"""

from __future__ import annotations

from tilebase.art import spike_drawer, tile_drawer
from tilebase.geom import Rect, Vec2
from tilebase.move import Body
from tilebase.tiles import Cell, TileDef, World, cells_overlapping, define

# Spikes are drawn in the bottom third of the cell. Hurt starts at the tips.
SPIKE_TOP = 0.68

LEGEND = (
    "# stone solid, - wooden bridge solid, = gold platform you can jump up through, "
    "b crate solid, D door solid, ^ spikes kill, ~ ice solid and slippery, "
    "* red spring solid and bounces you high, L lava kills on touch, "
    "c cracked rock solid until you stand on it, E exit flag, . air, P player"
)


def _empty(screen: object, rect: Rect) -> None:
    return None


def _ice(screen: object, rect: Rect) -> None:
    import pygame

    box = pygame.Rect(round(rect.x), round(rect.y), round(rect.w), round(rect.h))
    pygame.draw.rect(screen, (150, 215, 245), box)
    pygame.draw.rect(screen, (235, 250, 255), (box.x, box.y, box.w, max(2, box.h // 6)))
    pygame.draw.line(
        screen, (255, 255, 255), (box.x + box.w * 0.2, box.y + box.h * 0.75),
        (box.x + box.w * 0.55, box.y + box.h * 0.35), 2,
    )
    pygame.draw.rect(screen, (70, 140, 190), box, 1)


def _spring(screen: object, rect: Rect) -> None:
    import pygame

    x, y, w, h = round(rect.x), round(rect.y), round(rect.w), round(rect.h)
    pygame.draw.rect(screen, (90, 90, 100), (x + 2, y + h - h // 5, w - 4, h // 5))
    coil_top = y + h // 3
    coil_bottom = y + h - h // 5
    steps = 4
    for i in range(steps):
        y0 = coil_top + (coil_bottom - coil_top) * i / steps
        y1 = coil_top + (coil_bottom - coil_top) * (i + 1) / steps
        a, b = (x + w // 4, x + w - w // 4) if i % 2 == 0 else (x + w - w // 4, x + w // 4)
        pygame.draw.line(screen, (200, 200, 210), (a, y0), (b, y1), 3)
    pygame.draw.rect(screen, (220, 40, 40), (x + 1, y, w - 2, h // 3), border_radius=4)
    pygame.draw.rect(screen, (255, 150, 150), (x + 4, y + 2, w - 8, 3))


def _lava(screen: object, rect: Rect) -> None:
    import pygame

    x, y, w, h = round(rect.x), round(rect.y), round(rect.w), round(rect.h)
    pygame.draw.rect(screen, (200, 40, 10), (x, y, w, h))
    pygame.draw.rect(screen, (255, 140, 0), (x, y, w, h // 4))
    pygame.draw.circle(screen, (255, 220, 60), (x + w // 3, y + h // 2), max(2, w // 10))
    pygame.draw.circle(screen, (255, 180, 40), (x + 2 * w // 3, y + 3 * h // 4), max(2, w // 12))


def _crumble(screen: object, rect: Rect) -> None:
    import pygame

    x, y, w, h = round(rect.x), round(rect.y), round(rect.w), round(rect.h)
    pygame.draw.rect(screen, (140, 105, 75), (x, y, w, h))
    crack = (60, 40, 25)
    pygame.draw.lines(
        screen, crack, False,
        [(x + w * 0.5, y), (x + w * 0.4, y + h * 0.35), (x + w * 0.6, y + h * 0.6), (x + w * 0.45, y + h)],
        2,
    )
    pygame.draw.line(screen, crack, (x, y + h * 0.5), (x + w * 0.4, y + h * 0.35), 2)
    pygame.draw.rect(screen, (90, 65, 45), (x, y, w, h), 1)


TILES: tuple[TileDef, ...] = (
    define(".", id="empty", draw=_empty, marks=frozenset()),
    define("#", id="solid", draw=tile_drawer("solid"), marks=frozenset({"blocks"})),
    define("-", id="bridge", draw=tile_drawer("bridge"), marks=frozenset({"blocks"})),
    define("=", id="platform", draw=tile_drawer("platform"), marks=frozenset({"oneway"})),
    define("b", id="block", draw=tile_drawer("block"), marks=frozenset({"blocks"})),
    define("D", id="door", draw=tile_drawer("door"), marks=frozenset({"blocks"})),
    define("^", id="spike", draw=spike_drawer(), marks=frozenset({"hazard"})),
    define("~", id="slippery_ice", draw=_ice, marks=frozenset({"blocks", "slick"})),
    define("*", id="spring", draw=_spring, marks=frozenset({"blocks", "bounce"})),
    define("L", id="lava", draw=_lava, marks=frozenset({"burns"})),
    define("c", id="crumble", draw=_crumble, marks=frozenset({"blocks", "crumble"})),
    define("E", id="exit", draw=tile_drawer("exit"), marks=frozenset({"goal"})),
)

_GLYPH = {tile.id: tile.ch for tile in TILES}


def level_tiles() -> tuple[TileDef, ...]:
    return TILES


def glyph_for(tile_id: str) -> str:
    return _GLYPH.get(tile_id, "?")


def blocks_cell(cell: Cell, body: Body, delta: Vec2) -> bool:
    """Solid kinds stop every side. A platform only stops a landing from above."""
    if "blocks" in cell.marks:
        return True
    if "oneway" not in cell.marks or delta.y <= 0:
        return False
    return body.rect.y + body.rect.h <= cell.rect.y + 0.5


def overlaps_mark(world: World, rect: Rect, mark: str) -> bool:
    return any(mark in cell.marks for cell in cells_overlapping(world, rect))


def under_feet(world: World, rect: Rect) -> tuple[Cell, ...]:
    """The cells in the one-pixel strip just below the body."""
    return tuple(cells_overlapping(world, Rect(rect.x, rect.y + rect.h, rect.w, 1)))


def hurt_at(world: World, rect: Rect) -> bool:
    """True when the body touches lava or reaches the spikes, not the air above them."""
    for cell in cells_overlapping(world, rect):
        if "burns" in cell.marks:
            return True
        if "hazard" not in cell.marks:
            continue
        tip = cell.rect.y + cell.rect.h * SPIKE_TOP
        if rect.y + rect.h > tip and rect.y < cell.rect.y + cell.rect.h:
            return True
    return False


def grid_text(world: World, player: Rect) -> str:
    """The level as glyph rows under a column ruler, then every named tile run with its coordinates.

    The model miscounts columns in a 30-wide row, so runs like `lava: row 8, cols 9-14` are spelled out."""
    everything = Rect(0, 0, world.cols * world.tile_size, world.rows * world.tile_size)
    cells = {(c.col, c.row): c for c in cells_overlapping(world, everything)}
    glyphs = {pos: glyph_for(c.id) for pos, c in cells.items()}
    for c in cells_overlapping(world, player):
        glyphs[(c.col, c.row)] = "P"
    tens = "".join(str(col // 10 % 10) for col in range(world.cols))
    ones = "".join(str(col % 10) for col in range(world.cols))
    lines = [f"col  {tens}", f"     {ones}"]
    for row in range(world.rows):
        lines.append(f"row{row} " + "".join(glyphs[(col, row)] for col in range(world.cols)))
    lines.append("")
    for row in range(world.rows):
        col = 0
        while col < world.cols:
            glyph = glyphs[(col, row)]
            end = col
            while end + 1 < world.cols and glyphs[(end + 1, row)] == glyph:
                end += 1
            if glyph not in (".", "#"):
                name = "player" if glyph == "P" else cells[(col, row)].id
                span = f"col {col}" if end == col else f"cols {col}-{end}"
                lines.append(f"{name}: row {row}, {span}")
            col = end + 1
    return "\n".join(lines)
