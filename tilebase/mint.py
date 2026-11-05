"""The paid level: every placement costs a token, and the tokens are out on the map.

The player starts broke. Four tokens sit on the climb at the left. The lava pit
is wider than any dash-jump, and the wall under the flag is taller than a jump,
so finishing takes a plank, a crate, and a step: three tokens and one spare.
"""

from __future__ import annotations

from tilebase.box import TILE, Level
from tilebase.contraptions import Stock
from tilebase.edit import define_entities
from tilebase.geom import Rect, Vec2
from tilebase.kinds import level_tiles
from tilebase.tiles import World, define, load_map
from tilebase.tokens import TOKEN_MARK, draw_token

ROWS = (
    "##############################",
    "#..........................EE#",
    "#.o........................EE#",
    "#===...o..................####",
    "#....o....................####",
    "#...===...................####",
    "#.o.......................####",
    "#.........................####",
    "########LLLLLLLLLLLLLL########",
)
EXIT = frozenset({(27, 1), (28, 1), (27, 2), (28, 2)})
STOCK: Stock = ("plank", "plank", "crate", "step")


def open_level() -> Level:
    loaded = load_map(
        ROWS,
        (
            *level_tiles(),
            define("o", id="token", draw=draw_token, marks=frozenset({TOKEN_MARK})),
        ),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    spawn = Vec2(TILE * 1 + (TILE - 22) / 2, loaded.rows * TILE - TILE - 22)
    _world, entities = define_entities(
        loaded,
        (),
        bounds=Rect(0, 0, loaded.cols * TILE, loaded.rows * TILE),
        exit_tiles=EXIT,
        spawn_rect=Rect(spawn.x, spawn.y, 22, 22),
    )
    return Level(loaded, entities, spawn, STOCK)
