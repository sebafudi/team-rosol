"""Night-ruins example room. The default demo level is unchanged.

Run with `python -m tilebase.city`.

The room follows the cable-lift chamber: a snowy ledge on the left, stone
arches, two ice masses, and a pair of lifts hanging in the center. Stand on
a lift and it climbs to the ice beside it, pauses, then returns. From either
ice shelf a jump reaches the sill under the crystal.
"""

from __future__ import annotations

import math

from tilebase.art import tile_drawer
from tilebase.geom import Rect, Size, Vec2
from tilebase.movers import Mover, ride_step
from tilebase.play import (
    DASH_FREEZE,
    DASH_KEYS,
    JUMP_KEYS,
    TICK,
    Latch,
    _codes,
    axis,
    blocks,
    clamp_cam,
    follow,
    lerp,
    read_held,
    ticks_for,
)
from tilebase.tiles import World, cells_overlapping, define, load_map

TILE = 32
# The whole room fits the window, the way the reference chamber is one screen.
VIEW = Size(30 * TILE, 17 * TILE)

#          012345678901234567890123456789
ROWS = (
    "..####......######..........#.",
    "..#..#......#....#..........i.",
    "..#..#......#....#..........i.",
    "..#..#......#..o.#..........#.",
    "..####......................#.",
    "....##....############......#.",
    "....##......................#.",
    "....##iiii............iiii..#.",
    "....##iiii............iiii..##",
    "....##iiii............iiii....",
    "....##....................####",
    "...S..........................",
    "iiisssss......................",
    "########..............########",
    "..............................",
    "..............................",
    "..............................",
)

# Sagging cables between the ice masses, in world pixels.
CHAINS = (
    ((10 * TILE, 8 * TILE + 8), (22 * TILE, 8 * TILE + 18), 28.0),
    ((10 * TILE, 9 * TILE + 4), (22 * TILE, 9 * TILE + 10), 36.0),
    ((6 * TILE, 7 * TILE), (14 * TILE, 5 * TILE + 20), 18.0),
)


def _draw_empty(screen: object, rect: Rect) -> None:
    return None


def _draw_snow(screen: object, rect: Rect) -> None:
    import pygame

    tile_drawer("solid")(screen, rect)
    pygame.draw.rect(screen, (248, 252, 255), (rect.x, rect.y, rect.w, 8))


def _draw_ice(screen: object, rect: Rect) -> None:
    import pygame

    tile_drawer("solid")(screen, rect)
    veil = pygame.Surface((max(1, round(rect.w)), max(1, round(rect.h))), pygame.SRCALPHA)
    veil.fill((70, 160, 235, 130))
    screen.blit(veil, (round(rect.x), round(rect.y)))


def _draw_crystal(screen: object, rect: Rect) -> None:
    import pygame

    cx = round(rect.x + rect.w / 2)
    cy = round(rect.y + rect.h / 2)
    pygame.draw.circle(screen, (150, 190, 255), (cx, cy), 14)
    pygame.draw.circle(screen, (210, 235, 255), (cx, cy), 8)
    pygame.draw.circle(screen, (255, 255, 255), (cx - 2, cy - 3), 3)


def world() -> World:
    rows = tuple(row.replace("S", ".") for row in ROWS)
    loaded = load_map(
        rows,
        (
            define(".", id="empty", draw=_draw_empty, marks=frozenset()),
            define("#", id="solid", draw=tile_drawer("solid"), marks=frozenset({"blocks"})),
            define("s", id="snow", draw=_draw_snow, marks=frozenset({"blocks"})),
            define("i", id="ice", draw=_draw_ice, marks=frozenset({"blocks"})),
            define("o", id="crystal", draw=_draw_crystal, marks=frozenset({"goal"})),
        ),
        tile_size=TILE,
    )
    if not isinstance(loaded, World):
        raise RuntimeError(loaded)
    return loaded


def lifts() -> tuple[Mover, ...]:
    """The two center platforms. Each docks level with the ice shelf beside it."""
    top = 7 * TILE
    home = 15 * TILE
    return (
        Mover("left", x=10 * TILE, y=home, w=4 * TILE, h=24, home=home, goal=top, pulley=6 * TILE + 14),
        Mover("right", x=18 * TILE, y=home, w=4 * TILE, h=24, home=home, goal=top, pulley=6 * TILE + 20),
    )


def spawn_point(rows: tuple[str, ...] = ROWS) -> Vec2:
    for r, row in enumerate(rows):
        c = row.find("S")
        if c >= 0:
            return Vec2(c * TILE + (TILE - 22) / 2, r * TILE + TILE - 22)
    return Vec2(TILE, TILE)


def reached_crystal(level: World, rect: Rect) -> bool:
    return any(cell.id == "crystal" for cell in cells_overlapping(level, rect))


def _chain(screen: object, origin: Vec2, a: tuple[float, float], b: tuple[float, float], sag: float) -> None:
    import pygame

    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + sag)
    points = tuple(
        (round(p[0] - origin.x), round(p[1] - origin.y)) for p in (a, mid, b)
    )
    pygame.draw.lines(screen, (186, 198, 214), False, points, 2)


def _sign(screen: object, origin: Vec2) -> None:
    import pygame

    x = round(3 * TILE + 4 - origin.x)
    y = round(1 * TILE + 6 - origin.y)
    pygame.draw.rect(screen, (232, 236, 226), (x, y, 52, 36))
    pygame.draw.rect(screen, (64, 140, 72), (x, y, 52, 36), 3)
    pygame.draw.line(screen, (64, 140, 72), (x + 8, y + 24), (x + 22, y + 14), 2)
    pygame.draw.line(screen, (64, 140, 72), (x + 22, y + 14), (x + 40, y + 20), 2)


def _icicles(screen: object, origin: Vec2) -> None:
    import pygame

    for col in range(13, 17):
        x = col * TILE + 10 - origin.x
        y = TILE - origin.y
        pygame.draw.polygon(
            screen,
            (236, 244, 255),
            ((round(x), round(y)), (round(x + 8), round(y)), (round(x + 4), round(y + 14))),
        )


def _snow_cap(screen: object, origin: Vec2) -> None:
    import pygame

    pygame.draw.circle(screen, (120, 190, 255), (round(28 * TILE + 10 - origin.x), round(36 - origin.y)), 26)
    pygame.draw.circle(screen, (186, 224, 255), (round(27 * TILE + 8 - origin.x), round(28 - origin.y)), 16)


def draw_lift(screen: object, mover: Mover, origin: Vec2, time: float) -> None:
    import pygame

    x = mover.x - origin.x
    y = mover.y - origin.y
    cx = x + mover.w / 2
    pulley_y = mover.pulley - origin.y
    pygame.draw.line(screen, (150, 96, 62), (round(cx), round(pulley_y)), (round(cx), round(y)), 3)
    pygame.draw.circle(screen, (96, 64, 48), (round(cx), round(pulley_y)), 7)
    pygame.draw.circle(screen, (40, 28, 24), (round(cx), round(pulley_y)), 3)
    body = pygame.Rect(round(x), round(y), round(mover.w), round(mover.h))
    pygame.draw.rect(screen, (72, 80, 92), body)
    pygame.draw.rect(screen, (176, 186, 198), body.inflate(-4, -4))
    for i in range(3):
        ox = x + mover.w * (i + 1) / 4
        pygame.draw.circle(screen, (90, 98, 110), (round(ox), round(y + mover.h / 2)), 7, 2)
    pulse = 0.65 + 0.35 * math.sin(time * 6.0) if mover.phase == "wait" else 1.0
    green = (round(70 * pulse), round(210 * pulse), round(110 * pulse))
    pygame.draw.circle(screen, green, (round(cx), round(y + mover.h / 2)), 5)


def draw_scene(
    screen: object,
    level: World,
    movers: tuple[Mover, ...],
    origin: Vec2,
    time: float,
    cleared: bool,
) -> None:
    import pygame

    view = Rect(origin.x, origin.y, VIEW.w, VIEW.h)
    for cell in cells_overlapping(level, view):
        rect = cell.rect
        cell.draw(screen, Rect(rect.x - origin.x, rect.y - origin.y, rect.w, rect.h))
    for a, b, sag in CHAINS:
        _chain(screen, origin, a, b, sag)
    _sign(screen, origin)
    _icicles(screen, origin)
    _snow_cap(screen, origin)
    for mover in movers:
        draw_lift(screen, mover, origin, time)
    if cleared:
        banner = pygame.Rect(VIEW.w // 2 - 130, 16, 260, 28)
        pygame.draw.rect(screen, (16, 24, 48), banner)
        pygame.draw.rect(screen, (180, 210, 255), banner, 2)
        try:
            font = pygame.font.Font(None, 22)
        except (NotImplementedError, pygame.error):
            font = None
        if font is not None:
            text = font.render("Crystal reached", True, (220, 235, 255))
            screen.blit(text, text.get_rect(center=banner.center))


def main() -> None:
    import os

    import pygame

    from tilebase import art, blob, player

    os.environ.setdefault("SDL_HINT_RENDER_VSYNC", "1")
    pygame.init()
    screen = pygame.display.set_mode((VIEW.w, VIEW.h), pygame.SCALED | pygame.RESIZABLE, vsync=1)
    pygame.display.set_caption("Grok the Gap — city lifts")
    level = world()
    start = spawn_point()
    jump_codes = _codes(pygame, JUMP_KEYS)
    dash_codes = _codes(pygame, DASH_KEYS)
    pad = None
    if pygame.joystick.get_count() > 0:
        pad = pygame.joystick.Joystick(0)

    def reset() -> tuple[player.Player, tuple[Mover, ...], bool]:
        return player.spawn(start.x, start.y), lifts(), False

    p, movers, cleared = reset()
    prev_rect = p.body.rect
    look = blob.rest()
    puffs = blob.no_puffs()
    latch = Latch()
    acc = 0.0
    freeze = 0.0
    shake = 0.0
    tick_no = 0
    cam = clamp_cam(p.body.rect.center, level, VIEW)
    clock = pygame.time.Clock()
    last = pygame.time.get_ticks() / 1000.0
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    p, movers, cleared = reset()
                    prev_rect = p.body.rect
                if event.key in jump_codes:
                    latch = Latch(jump=True, dash=latch.dash)
                if event.key in dash_codes:
                    latch = Latch(jump=latch.jump, dash=True)
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    latch = Latch(jump=True, dash=latch.dash)
                elif event.button in (1, 2):
                    latch = Latch(jump=latch.jump, dash=True)

        now = pygame.time.get_ticks() / 1000.0
        frame_dt = now - last
        last = now
        held = read_held(pygame, pygame.key.get_pressed(), pad)
        ix = axis(held.left, held.right)
        iy = axis(held.up, held.down)

        if freeze > 0:
            freeze -= frame_dt
            n = 0
        else:
            n, acc = ticks_for(acc, frame_dt)
        for _ in range(n):
            if cleared:
                latch = Latch()
                break
            inp = player.Input(
                x=ix,
                y=iy,
                jump=held.jump or latch.jump,
                jump_pressed=latch.jump,
                dash_pressed=latch.dash,
            )
            latch = Latch()
            prev_rect = p.body.rect
            p, movers = ride_step(p, movers, level, blocks, inp, TICK)
            tick_no += 1
            look = blob.update_look(look, p, ix, iy, TICK)
            feet = Vec2(p.body.rect.center.x, p.body.rect.y + p.body.rect.h)
            puffs = blob.emit_puffs(puffs, p, feet, tick_no)
            puffs = blob.update_puffs(puffs, TICK)
            if reached_crystal(level, p.body.rect):
                cleared = True
            if "dash" in p.events:
                freeze = DASH_FREEZE
                shake = max(shake, 0.12)
                break
            if "land" in p.events and p.impact > 800:
                shake = max(shake, 0.06)
            if p.body.rect.y > level.rows * TILE + 64:
                p, movers, cleared = reset()
                prev_rect = p.body.rect

        alpha = 0.0 if freeze > 0 else acc / TICK
        draw_x = lerp(prev_rect.x, p.body.rect.x, alpha)
        draw_y = lerp(prev_rect.y, p.body.rect.y, alpha)
        center = Vec2(draw_x + p.body.rect.w / 2, draw_y + p.body.rect.h / 2)
        lead = Vec2(center.x + p.facing * 40 + p.vel.x * 0.08, center.y)
        cam = clamp_cam(follow(cam, lead, frame_dt), level, VIEW)
        shake = max(0.0, shake - frame_dt)
        jitter = 3.0 * shake / 0.12
        origin = Vec2(
            round(cam.x - VIEW.w / 2 + math.sin(now * 91.0) * jitter),
            round(cam.y - VIEW.h / 2 + math.cos(now * 77.0) * jitter),
        )
        art.draw_backdrop(screen, cam, Size(level.cols * TILE, level.rows * TILE), VIEW)
        draw_scene(screen, level, movers, origin, now, cleared)
        blob.draw_puffs(screen, puffs, origin)
        art.draw_player(
            screen,
            Vec2(center.x - origin.x, center.y - origin.y),
            p,
            look,
            dashes_left=p.dashes_left,
        )
        pygame.display.flip()
        clock.tick(0 if _has_vsync(pygame) else 240)
    pygame.quit()


def _has_vsync(pygame: object) -> bool:
    try:
        return pygame.display.is_vsync()
    except (AttributeError, pygame.error):
        return False


if __name__ == "__main__":
    main()
