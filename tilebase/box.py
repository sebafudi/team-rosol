"""The opening level: its tiles, exit, spawn, and the contraptions it hands the agent.

The other tiles are landmarks with their own behavior, so a prompt can say
where: the spikes, the bridge, the door, the platform, the crate, the flag.
"""

from __future__ import annotations

from dataclasses import dataclass

from tilebase.contraptions import STARTING_STOCK, Stock
from tilebase.edit import Entities, define_entities
from tilebase.edit_integration import tile_rects
from tilebase.geom import Rect, Size, Vec2
from tilebase.kinds import level_tiles
from tilebase.tiles import World, cells_overlapping, load_map

TILE = 32

# The pit is wider than a dash-jump. Spikes mark where a contraption belongs.
# The shelf on the left stays over stone, short of the lip. The start floor is
# ice, a spring sits at the lip, lava fills the pit's left half, and cracked
# rock hangs over it: each kind is something a prompt can name.
ROWS = (
    "##############################",
    "#............................#",
    "#............................#",
    "#............................#",
    "#..........ccc...............#",
    "#............................#",
    "#---==b....................EE#",
    "#.......*................D.EE#",
    "#~~~~~~~#LLLLLL^^.......######",
)
EXIT = frozenset({(27, 6), (28, 6), (27, 7), (28, 7)})


@dataclass(frozen=True)
class Level:
    """`tokens` is the starting balance when each prompt costs one; None is free.

    A checkpoint is a zone and the spawn it moves the respawn to, in map order.
    """

    world: World
    entities: Entities
    spawn: Vec2
    stock: Stock
    tokens: int | None = None
    checkpoints: tuple[tuple[Rect, Vec2], ...] = ()
    hint: str = ""


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
    return Level(loaded, entities, spawn, STARTING_STOCK)


def level_surface(
    world: World,
    center: Vec2,
    player: object,
    look: object,
    dashes_left: int,
) -> object:
    """The whole level, one pixel per game pixel, with the player and exit."""
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
