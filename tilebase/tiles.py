from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from tilebase.geom import Rect, Vec2

DrawFn = Callable[[object, Rect], None]


@dataclass(frozen=True)
class TileDef:
    ch: str
    id: str
    draw: DrawFn
    marks: frozenset[str]


def define(ch: str, *, id: str, draw: DrawFn, marks: frozenset[str]) -> TileDef:
    return TileDef(ch=ch, id=id, draw=draw, marks=marks)


@dataclass(frozen=True)
class Cell:
    id: str
    marks: frozenset[str]
    rect: Rect
    col: int
    row: int
    draw: DrawFn


@dataclass(frozen=True)
class UnknownChar:
    ch: str
    row: int
    col: int


@dataclass(frozen=True)
class DuplicateChar:
    ch: str


@dataclass(frozen=True)
class DuplicateId:
    id: str


@dataclass(frozen=True)
class BadTileChar:
    ch: str


@dataclass(frozen=True)
class RaggedRows:
    lengths: tuple[int, ...]


@dataclass(frozen=True)
class BadTileSize:
    tile_size: int


@dataclass(frozen=True)
class OutOfBounds:
    col: int
    row: int


@dataclass(frozen=True)
class UnknownId:
    id: str


@dataclass(frozen=True)
class World:
    tile_size: int
    cols: int
    rows: int
    _defs: tuple[TileDef, ...]
    _index: tuple[int, ...]


LoadResult = (
    World
    | UnknownChar
    | DuplicateChar
    | DuplicateId
    | BadTileChar
    | RaggedRows
    | BadTileSize
)
PutResult = World | OutOfBounds | UnknownId


def load_map(
    rows: tuple[str, ...],
    tiles: tuple[TileDef, ...],
    *,
    tile_size: int,
) -> LoadResult:
    if tile_size < 1:
        return BadTileSize(tile_size)
    if not rows:
        return RaggedRows(())
    widths = tuple(len(row) for row in rows)
    if len(set(widths)) != 1:
        return RaggedRows(widths)

    by_ch: dict[str, int] = {}
    seen_ids: set[str] = set()
    for index, tile in enumerate(tiles):
        if len(tile.ch) != 1:
            return BadTileChar(tile.ch)
        if tile.ch in by_ch:
            return DuplicateChar(tile.ch)
        if tile.id in seen_ids:
            return DuplicateId(tile.id)
        by_ch[tile.ch] = index
        seen_ids.add(tile.id)

    index_grid: list[int] = []
    for row_i, row in enumerate(rows):
        for col_i, ch in enumerate(row):
            found = by_ch.get(ch)
            if found is None:
                return UnknownChar(ch, row_i, col_i)
            index_grid.append(found)

    return World(
        tile_size=tile_size,
        cols=widths[0],
        rows=len(rows),
        _defs=tiles,
        _index=tuple(index_grid),
    )


def put_cell(world: World, col: int, row: int, tile_id: str) -> PutResult:
    """Return a new world with one cell replaced. Map edits copy the grid."""
    if not (0 <= col < world.cols and 0 <= row < world.rows):
        return OutOfBounds(col, row)
    found = next((i for i, tile in enumerate(world._defs) if tile.id == tile_id), None)
    if found is None:
        return UnknownId(tile_id)
    grid = list(world._index)
    grid[row * world.cols + col] = found
    return World(
        tile_size=world.tile_size,
        cols=world.cols,
        rows=world.rows,
        _defs=world._defs,
        _index=tuple(grid),
    )


def cell_at(world: World, point: Vec2) -> Cell | None:
    col = math.floor(point.x / world.tile_size)
    row = math.floor(point.y / world.tile_size)
    if not (0 <= col < world.cols and 0 <= row < world.rows):
        return None
    return _cell(world, col, row)


def cells_overlapping(world: World, rect: Rect) -> tuple[Cell, ...]:
    if rect.w <= 0 or rect.h <= 0 or world.cols == 0 or world.rows == 0:
        return ()
    size = world.tile_size
    min_col = max(0, math.floor(rect.x / size))
    max_col = min(world.cols - 1, math.floor((rect.x + rect.w - 1e-9) / size))
    min_row = max(0, math.floor(rect.y / size))
    max_row = min(world.rows - 1, math.floor((rect.y + rect.h - 1e-9) / size))
    if min_col > max_col or min_row > max_row:
        return ()
    return tuple(
        _cell(world, col, row)
        for row in range(min_row, max_row + 1)
        for col in range(min_col, max_col + 1)
    )


def _cell(world: World, col: int, row: int) -> Cell:
    tile = world._defs[world._index[row * world.cols + col]]
    size = float(world.tile_size)
    return Cell(
        id=tile.id,
        marks=tile.marks,
        rect=Rect(col * size, row * size, size, size),
        col=col,
        row=row,
        draw=tile.draw,
    )


def glyph_rows(world: World) -> tuple[str, ...]:
    """The world as map characters, one string per row, edits included."""
    return tuple(
        "".join(world._defs[world._index[row * world.cols + col]].ch for col in range(world.cols))
        for row in range(world.rows)
    )
