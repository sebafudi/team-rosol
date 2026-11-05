"""One-time contraptions the agent can place. Each is a small pattern of real tiles.

A level hands the agent a stock: a tuple of contraption ids, repeats allowed.
Placing one writes its tiles into the world and removes one copy from the stock.
Nothing is ever returned to the stock.
"""

from __future__ import annotations

from dataclasses import dataclass

from tilebase.edit import Entities
from tilebase.geom import Rect, Vec2
from tilebase.tiles import World, cell_at, put_cell

# Placing may overwrite air and hazards (that is how a crate covers spikes).
# Anything the player can already stand on, jump through, or finish on stays,
# and so do token pickups, or a careless placement could eat the next prompt.
PROTECTED_MARKS = frozenset({"blocks", "oneway", "goal", "token"})

Stock = tuple[str, ...]


@dataclass(frozen=True)
class Contraption:
    """`cells` are (dx, dy, tile id) from the top-left tile the agent names."""

    id: str
    summary: str
    cells: tuple[tuple[int, int, str], ...]

    @property
    def cols(self) -> int:
        return 1 + max(dx for dx, _dy, _t in self.cells)

    @property
    def rows(self) -> int:
        return 1 + max(dy for _dx, dy, _t in self.cells)


def _fill(tile: str, cols: int, rows: int) -> tuple[tuple[int, int, str], ...]:
    return tuple((dx, dy, tile) for dy in range(rows) for dx in range(cols))


CATALOG = (
    Contraption("crate", "2 wide, 2 tall solid crate", _fill("block", 2, 2)),
    Contraption("plank", "3 wide, 1 tall solid wooden bridge", _fill("bridge", 3, 1)),
    Contraption("step", "3 wide, 1 tall gold platform you can jump up through", _fill("platform", 3, 1)),
    Contraption("spring", "1 tile red spring that bounces you high", _fill("spring", 1, 1)),
)
_BY_ID = {c.id: c for c in CATALOG}

# What the opening level starts with: enough to bridge the pit once.
STARTING_STOCK: Stock = ("crate", "plank", "plank", "step", "spring")


def contraption(contraption_id: str) -> Contraption | None:
    return _BY_ID.get(contraption_id)


def available(stock: Stock) -> tuple[Contraption, ...]:
    """Distinct contraptions still in stock, in catalog order."""
    return tuple(c for c in CATALOG if c.id in stock)


def stock_line(stock: Stock) -> str:
    """'crate 1  plank 2' for the HUD."""
    return "  ".join(f"{c.id} {stock.count(c.id)}" for c in available(stock))


def describe(stock: Stock) -> str:
    """The stock as the model reads it."""
    return "; ".join(f"{c.id} x{stock.count(c.id)} ({c.summary})" for c in available(stock))


@dataclass(frozen=True)
class Placement:
    world: World
    stock: Stock


@dataclass(frozen=True)
class Refused:
    reason: str


def place(
    world: World,
    entities: Entities,
    stock: Stock,
    contraption_id: str,
    col: int,
    row: int,
    player: Rect,
) -> Placement | Refused:
    """Write the contraption's tiles with its top-left at (col, row) and spend one copy."""
    shape = _BY_ID.get(contraption_id)
    if shape is None or contraption_id not in stock:
        return Refused(f"no {contraption_id} left")
    size = world.tile_size
    for dx, dy, _tile in shape.cells:
        c, r = col + dx, row + dy
        cell = cell_at(world, Vec2(c * size + 1, r * size + 1))
        if cell is None:
            return Refused(f"{shape.id} hangs off the map")
        if (c, r) in entities.exit_tiles or PROTECTED_MARKS & cell.marks:
            return Refused(f"{shape.id} needs free air at {c},{r}")
        rect = Rect(c * size, r * size, size, size)
        if _overlap(rect, player) or (
            entities.spawn_rect is not None and _overlap(rect, entities.spawn_rect)
        ):
            return Refused(f"{shape.id} would land on the player at {c},{r}")
    for dx, dy, tile in shape.cells:
        placed = put_cell(world, col + dx, row + dy, tile)
        assert isinstance(placed, World)
        world = placed
    index = stock.index(contraption_id)
    return Placement(world, stock[:index] + stock[index + 1 :])


def _overlap(a: Rect, b: Rect) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    )
