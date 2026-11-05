from tilebase.geom import Rect, Size, Vec2
from tilebase.loop import run
from tilebase.move import Body, Frame
from tilebase.tiles import Cell, World, define, load_map

TILE = 32
SCREEN = Size(320, 180)

ROWS = (
    "####################",
    "#..................#",
    "#..................#",
    "#..####............#",
    "#..................#",
    "#.............###..#",
    "#..................#",
    "#..................#",
    "####################",
)


def _rect(screen: object, rect: Rect, color: tuple[int, int, int]) -> None:
    import pygame

    pygame.draw.rect(
        screen,
        color,
        (int(rect.x), int(rect.y), int(rect.w), int(rect.h)),
    )


def draw_empty(screen: object, rect: Rect) -> None:
    return None


def draw_solid(screen: object, rect: Rect) -> None:
    _rect(screen, rect, (48, 48, 56))


def draw_body(screen: object, rect: Rect) -> None:
    _rect(screen, rect, (220, 200, 80))


def blocks(cell: Cell, body: Body, delta: Vec2) -> bool:
    return "blocks" in cell.marks


def plan_move(frame: Frame) -> Vec2:
    """Arrow keys become a delta. A later platformer replaces this function."""
    speed = 120.0
    dx = 0.0
    dy = 0.0
    if frame.keys.left:
        dx -= speed * frame.dt
    if frame.keys.right:
        dx += speed * frame.dt
    if frame.keys.up:
        dy -= speed * frame.dt
    if frame.keys.down:
        dy += speed * frame.dt
    return Vec2(dx, dy)


def world() -> World:
    loaded = load_map(
        ROWS,
        (
            define(".", id="empty", draw=draw_empty, marks=frozenset()),
            define("#", id="solid", draw=draw_solid, marks=frozenset({"blocks"})),
        ),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    return loaded


def main() -> None:
    run(
        world=world(),
        body=Body(Rect(32, 32, 12, 14)),
        screen_size=SCREEN,
        plan_move=plan_move,
        blocks=blocks,
        draw_body=draw_body,
    )
