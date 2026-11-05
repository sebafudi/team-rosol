"""Tile kinds a player can name, and the model can read.

The character is the glyph in the grid sent with a prompt. The marks decide
what the body does:

- blocks: solid on every side (stone, the wooden bridge, a crate, a shut door)
- oneway: jump up through it and land on it (the gold platform)
- hazard: the lower band kills (spikes sit in the bottom of the cell)
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
    "b crate solid, D door solid, ^ spikes kill, E exit flag, . air, P player, B the box"
)


def _empty(screen: object, rect: Rect) -> None:
    return None


TILES: tuple[TileDef, ...] = (
    define(".", id="empty", draw=_empty, marks=frozenset()),
    define("#", id="solid", draw=tile_drawer("solid"), marks=frozenset({"blocks"})),
    define("-", id="bridge", draw=tile_drawer("bridge"), marks=frozenset({"blocks"})),
    define("=", id="platform", draw=tile_drawer("platform"), marks=frozenset({"oneway"})),
    define("b", id="block", draw=tile_drawer("block"), marks=frozenset({"blocks"})),
    define("D", id="door", draw=tile_drawer("door"), marks=frozenset({"blocks"})),
    define("^", id="spike", draw=spike_drawer(), marks=frozenset({"hazard"})),
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


def hurt_at(world: World, rect: Rect) -> bool:
    """True when the body reaches the spikes, not the empty air above them."""
    for cell in cells_overlapping(world, rect):
        if "hazard" not in cell.marks:
            continue
        tip = cell.rect.y + cell.rect.h * SPIKE_TOP
        if rect.y + rect.h > tip and rect.y < cell.rect.y + cell.rect.h:
            return True
    return False
