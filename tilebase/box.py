"""One 64 by 64 box. The model may place it, and nothing else."""

from __future__ import annotations

from dataclasses import dataclass

from tilebase.art import tile_drawer
from tilebase.edit import (
    Command,
    EditResult,
    Entities,
    define_entities,
    apply_edit,
    find_entity,
)
from tilebase.edit_integration import tile_rects
from tilebase.geom import Rect, Vec2
from tilebase.tiles import World, define, load_map

TILE = 32
SPAN = 2
BOX_ID = "box"

# Eight missing floor tiles. A dash covers about four and a half, so the
# gap stays a fall until the box sits in it.
ROWS = (
    "####################",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "####........########",
)
EXIT = frozenset({(16, 7)})


@dataclass(frozen=True)
class Level:
    world: World
    entities: Entities
    spawn: Vec2


def box_tiles(col: int, row: int) -> tuple[tuple[int, int], ...]:
    """Top-left tile plus the other three. 2 by 2 tiles is 64 by 64 pixels."""
    return tuple(
        (col + dx, row + dy) for dy in range(SPAN) for dx in range(SPAN)
    )


def open_level() -> Level:
    loaded = load_map(
        ROWS,
        (
            define(".", id="empty", draw=lambda _s, _r: None, marks=frozenset()),
            define(
                "#",
                id="solid",
                draw=tile_drawer("solid"),
                marks=frozenset({"blocks"}),
            ),
        ),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    spawn = Vec2(TILE * 2, loaded.rows * TILE - TILE - 22)
    _world, entities = define_entities(
        loaded,
        (),
        bounds=Rect(0, 0, loaded.cols * TILE, loaded.rows * TILE),
        exit_tiles=EXIT,
        spawn_rect=Rect(spawn.x, spawn.y, 22, 22),
    )
    return Level(loaded, entities, spawn)


def place_box(world: World, entities: Entities, col: int, row: int) -> EditResult:
    """Put the one box so its top-left tile is `(col, row)`. A second call moves it."""
    tiles = box_tiles(col, row)
    current = find_entity(entities, BOX_ID)
    if current is None:
        return apply_edit(
            world, entities, Command(op="place", id=BOX_ID, tiles=tiles)
        )
    origin_col = min(c for c, _r in current.tiles)
    origin_row = min(r for _c, r in current.tiles)
    return apply_edit(
        world,
        entities,
        Command(op="move", id=BOX_ID, by=(col - origin_col, row - origin_row)),
    )


def render_map(world: World, entities: Entities, player: Vec2) -> str:
    """The grid the model sees. `#` solid, `B` the box, `E` the exit, `P` the player."""
    rows = [["." for _ in range(world.cols)] for _ in range(world.rows)]
    span = Rect(0, 0, world.cols * TILE, world.rows * TILE)
    from tilebase.tiles import cells_overlapping

    for cell in cells_overlapping(world, span):
        if "blocks" in cell.marks:
            rows[cell.row][cell.col] = "#"
    for col, row in entities.exit_tiles:
        rows[row][col] = "E"
    box = find_entity(entities, BOX_ID)
    if box is not None:
        for col, row in box.tiles:
            rows[row][col] = "B"
    prow = int(player.y // TILE)
    pcol = int(player.x // TILE)
    if 0 <= prow < world.rows and 0 <= pcol < world.cols and rows[prow][pcol] == ".":
        rows[prow][pcol] = "P"
    return "\n".join("".join(row) for row in rows)


def overlaps_exit(body: Rect, entities: Entities) -> bool:
    for rect in tile_rects(entities.exit_tiles, TILE):
        if not (
            body.x + body.w <= rect.x
            or rect.x + rect.w <= body.x
            or body.y + body.h <= rect.y
            or rect.y + rect.h <= body.y
        ):
            return True
    return False


def draw_marks(screen: object, origin: Vec2, entities: Entities) -> None:
    """Paint the box and the exit in screen space, on top of the tiles."""
    import pygame

    box = find_entity(entities, BOX_ID)
    if box is not None:
        for rect in tile_rects(frozenset(box.tiles), TILE):
            pygame.draw.rect(
                screen,
                (196, 112, 48),
                (int(rect.x - origin.x), int(rect.y - origin.y), TILE, TILE),
            )
    for rect in tile_rects(entities.exit_tiles, TILE):
        pygame.draw.rect(
            screen,
            (48, 120, 72),
            (int(rect.x - origin.x), int(rect.y - origin.y), TILE, TILE),
        )
