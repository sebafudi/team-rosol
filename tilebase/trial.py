"""TRIAL: three obstacles, one token per prompt, and you start with one token.

Every prompt costs a token, spent when the prompt is sent (the talk key is
released, or Enter is pressed on a typed one). A prompt the agent fails to
place hands the token back. The next token waits just past each obstacle, so
each prompt has to count:

1. The cliff is nine tiles of sheer stone, out of reach of a jump and dash.
   A spring at its foot throws you high enough to dash onto the top.
2. The lava lake is sixteen tiles wide, wider than any dash-jump. One stepping
   stone in the middle splits it into two jumps.
3. The spike tunnel has a low roof, so you cannot arc over it. A dash carries
   you about half way. You need somewhere to land in the middle.

The stock has one more contraption than there are tokens, so there is a spare
choice, not a spare prompt. Tab shows the whole map so you can plan.
"""

from __future__ import annotations

from tilebase.box import TILE, Level
from tilebase.edit import define_entities
from tilebase.geom import Rect, Vec2
from tilebase.kinds import level_tiles
from tilebase.tiles import World, define, load_map
from tilebase.tokens import TOKEN_MARK, draw_token

ROWS = (
    "##########################################################################",
    "#.............................#......................################....#",
    "#.............................#......................################....#",
    "#.............................#......................################....#",
    "#........................o....#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..#......................################....#",
    "#...................########..........................................EE.#",
    "#...................########......................o...................EE.#",
    "###############################LLLLLLLLLLLLLLLL#######^^^^^^^^^^^^^^######",
    "##########################################################################",
    "##########################################################################",
)

STOCK = ("crate", "plank", "step", "spring")
START_TOKENS = 1
HINT = "1 token, 1 prompt   tab map   v hold talk   r restart"


def _stand(col: int, row: int) -> Vec2:
    """Where a 22 px body stands in the tile at (col, row)."""
    return Vec2(col * TILE + (TILE - 22) / 2, row * TILE + TILE - 22)


def _zone(col0: int, col1: int, row0: int, row1: int) -> Rect:
    return Rect(col0 * TILE, row0 * TILE, (col1 - col0 + 1) * TILE, (row1 - row0 + 1) * TILE)


# On top of the cliff, at the foot of the drop past it, and past the lava.
CHECKPOINTS = (
    (_zone(20, 27, 4, 4), _stand(22, 4)),
    (_zone(28, 30, 12, 13), _stand(29, 13)),
    (_zone(47, 52, 12, 13), _stand(48, 13)),
)


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
    spawn = _stand(3, 13)
    exit_tiles = frozenset(
        (c, r) for r, row in enumerate(ROWS) for c, ch in enumerate(row) if ch == "E"
    )
    _world, entities = define_entities(
        loaded,
        (),
        bounds=Rect(0, 0, loaded.cols * TILE, loaded.rows * TILE),
        exit_tiles=exit_tiles,
        spawn_rect=Rect(spawn.x, spawn.y, 22, 22),
    )
    return Level(
        loaded,
        entities,
        spawn,
        STOCK,
        tokens=START_TOKENS,
        checkpoints=CHECKPOINTS,
        hint=HINT,
    )
