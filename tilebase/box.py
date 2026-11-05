"""One 64 by 64 box. The model may place it, and nothing else.

The other tiles are landmarks with their own behavior, so a prompt can say
where: the spikes, the bridge, the door, the platform, the crate, the flag.
"""

from __future__ import annotations

from dataclasses import dataclass

from tilebase.edit import (
    Command,
    EditResult,
    Entities,
    define_entities,
    apply_edit,
    find_entity,
)
from tilebase.edit_integration import tile_rects
from tilebase.geom import Rect, Size, Vec2
from tilebase.kinds import level_tiles
from tilebase.tiles import World, cells_overlapping, load_map

TILE = 32
SPAN = 2
BOX_ID = "box"

# The pit is wider than a dash-jump. Spikes mark where the box belongs.
# The shelf on the left stays over stone, short of the lip.
ROWS = (
    "##############################",
    "#............................#",
    "#............................#",
    "#............................#",
    "#............................#",
    "#............................#",
    "#---==b....................EE#",
    "#........................D.EE#",
    "#########......^^.......######",
)
EXIT = frozenset({(27, 6), (28, 6), (27, 7), (28, 7)})


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
        level_tiles(),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    spawn = Vec2(TILE * 4 + (TILE - 22) / 2, loaded.rows * TILE - TILE - 22)
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


def level_surface(
    world: World,
    entities: Entities,
    center: Vec2,
    player: object,
    look: object,
    dashes_left: int,
) -> object:
    """The whole level, one pixel per game pixel, with the player, box, and exit."""
    import pygame

    from tilebase import art

    width = world.cols * TILE
    height = world.rows * TILE
    surface = pygame.Surface((width, height))
    extent = Size(width, height)
    art.draw_backdrop(surface, Vec2(width / 2, height / 2), extent, extent)
    for cell in cells_overlapping(world, Rect(0, 0, width, height)):
        rect = cell.rect
        cell.draw(surface, Rect(rect.x, rect.y, rect.w, rect.h))
    art.draw_player(surface, center, player, look, dashes_left=dashes_left)
    draw_marks(surface, Vec2(0, 0), entities)
    return surface


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
    """Paint the placed box. The flag and the other kinds are real tiles."""
    import pygame

    box = find_entity(entities, BOX_ID)
    if box is None:
        return
    for rect in tile_rects(frozenset(box.tiles), TILE):
        pygame.draw.rect(
            screen,
            (196, 112, 48),
            (int(rect.x - origin.x), int(rect.y - origin.y), TILE, TILE),
        )
