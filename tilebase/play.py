"""Movement sandbox: fixed-step physics, event-driven input, smoothed camera.

Run with `python -m tilebase.play`. The map is a test bench for movement,
not a level.

Input latency budget: key events are drained right before each physics tick,
presses are latched as edges so a tap shorter than one tick still counts,
physics runs at 120 Hz, and the frame is drawn straight after the last tick.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tilebase.geom import Rect, Size, Vec2
from tilebase.move import Body
from tilebase.tiles import Cell, World, cells_overlapping, define, load_map

TILE = 32
VIEW = Size(640, 360)
WINDOW_SCALE = 2
TICK = 1.0 / 120.0
MAX_TICKS_PER_FRAME = 8
DASH_FREEZE = 0.05

SANDBOX = (
    "##############################################################",
    "#............................................................#",
    "#............................................................#",
    "#............................................................#",
    "#.....................................##.....................#",
    "#.....................................##.....................#",
    "#..........####.......................##.......#.............#",
    "#.....................#...............##.......#.............#",
    "#.....................#.........#.....##.......#......#####..#",
    "#.....................#.........#..............#.............#",
    "#...........S.........#...####..#..............#.............#",
    "#.............................#.#.....##.......#.............#",
    "#######....####...######......#.#.....##..#######..###########",
    "#######....####...######......#.#.....##..#######..###########",
    "##############################################################",
)


@dataclass(frozen=True)
class Held:
    left: bool
    right: bool
    up: bool
    down: bool
    jump: bool
    dash: bool


@dataclass(frozen=True)
class Latch:
    """Presses seen since the last physics tick. Cleared after each tick."""

    jump: bool = False
    dash: bool = False


def axis(neg: bool, pos: bool) -> int:
    return int(pos) - int(neg)


def ticks_for(acc: float, frame_dt: float) -> tuple[int, float]:
    """Fixed-step accumulator. Drops time beyond MAX_TICKS_PER_FRAME."""
    acc += min(frame_dt, TICK * MAX_TICKS_PER_FRAME)
    n = int(acc / TICK)
    return n, acc - n * TICK


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def follow(cam: Vec2, target: Vec2, dt: float, sharpness: float = 10.0) -> Vec2:
    """Frame-rate independent exponential follow."""
    t = 1.0 - math.exp(-sharpness * dt)
    return Vec2(lerp(cam.x, target.x, t), lerp(cam.y, target.y, t))


def clamp_cam(center: Vec2, world: World, view: Size) -> Vec2:
    w = world.cols * world.tile_size
    h = world.rows * world.tile_size
    half_w = view.w / 2
    half_h = view.h / 2
    x = min(max(center.x, half_w), max(half_w, w - half_w))
    y = min(max(center.y, half_h), max(half_h, h - half_h))
    return Vec2(x, y)


def blocks(cell: Cell, body: Body, delta: Vec2) -> bool:
    return "blocks" in cell.marks


def spawn_point(rows: tuple[str, ...]) -> Vec2:
    for r, row in enumerate(rows):
        c = row.find("S")
        if c >= 0:
            return Vec2(c * TILE + (TILE - 22) / 2, r * TILE + TILE - 22)
    return Vec2(TILE, TILE)


def _draw_solid(screen: object, rect: Rect) -> None:
    import pygame

    r = pygame.Rect(round(rect.x), round(rect.y), round(rect.w), round(rect.h))
    pygame.draw.rect(screen, (58, 44, 52), r)
    pygame.draw.rect(screen, (92, 66, 72), r, 1)


def _draw_empty(screen: object, rect: Rect) -> None:
    return None


def sandbox() -> World:
    loaded = load_map(
        tuple(row.replace("S", ".") for row in SANDBOX),
        (
            define(".", id="empty", draw=_draw_empty, marks=frozenset()),
            define("#", id="solid", draw=_draw_solid, marks=frozenset({"blocks"})),
        ),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    return loaded


JUMP_KEYS = ("K_SPACE", "K_c", "K_z", "K_k")
DASH_KEYS = ("K_x", "K_LSHIFT", "K_RSHIFT", "K_j")


def _codes(pygame: object, names: tuple[str, ...]) -> frozenset[int]:
    return frozenset(getattr(pygame, n) for n in names)


def read_held(pygame: object, pressed: object, pad: object | None) -> Held:
    def any_of(*names: str) -> bool:
        return any(pressed[getattr(pygame, n)] for n in names)

    left = any_of("K_LEFT", "K_a")
    right = any_of("K_RIGHT", "K_d")
    up = any_of("K_UP", "K_w")
    down = any_of("K_DOWN", "K_s")
    jump = any_of(*JUMP_KEYS)
    dash = any_of(*DASH_KEYS)
    if pad is not None:
        sx = pad.get_axis(0) if pad.get_numaxes() > 0 else 0.0
        sy = pad.get_axis(1) if pad.get_numaxes() > 1 else 0.0
        hx, hy = pad.get_hat(0) if pad.get_numhats() > 0 else (0, 0)
        dead = 0.35
        left = left or sx < -dead or hx < 0
        right = right or sx > dead or hx > 0
        up = up or sy < -dead or hy > 0
        down = down or sy > dead or hy < 0
        jump = jump or bool(pad.get_button(0))
        dash = dash or any(pad.get_button(b) for b in (1, 2) if b < pad.get_numbuttons())
    return Held(left, right, up, down, jump, dash)


def main() -> None:
    import os

    import pygame

    from tilebase import blob, player

    os.environ.setdefault("SDL_HINT_RENDER_VSYNC", "1")
    pygame.init()
    screen = pygame.display.set_mode(
        (VIEW.w, VIEW.h), pygame.SCALED | pygame.RESIZABLE, vsync=1
    )
    pygame.display.set_caption("team-rosol — movement sandbox")
    font = pygame.font.Font(None, 16)
    world = sandbox()
    start = spawn_point(SANDBOX)
    jump_codes = _codes(pygame, JUMP_KEYS)
    dash_codes = _codes(pygame, DASH_KEYS)
    pad = None
    if pygame.joystick.get_count() > 0:
        pad = pygame.joystick.Joystick(0)

    p = player.spawn(start.x, start.y)
    prev_rect = p.body.rect
    look = blob.rest()
    puffs = blob.no_puffs()
    latch = Latch()
    acc = 0.0
    freeze = 0.0
    shake = 0.0
    tick_no = 0
    show_debug = False
    cam = clamp_cam(p.body.rect.center, world, VIEW)
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
                    p = player.spawn(start.x, start.y)
                    prev_rect = p.body.rect
                elif event.key == pygame.K_F1:
                    show_debug = not show_debug
                if event.key in jump_codes:
                    latch = Latch(jump=True, dash=latch.dash)
                if event.key in dash_codes:
                    latch = Latch(jump=latch.jump, dash=True)
            elif event.type == pygame.JOYBUTTONDOWN:
                if event.button == 0:
                    latch = Latch(jump=True, dash=latch.dash)
                elif event.button in (1, 2):
                    latch = Latch(jump=latch.jump, dash=True)
            elif event.type == pygame.JOYDEVICEADDED and pad is None:
                pad = pygame.joystick.Joystick(event.device_index)

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
            inp = player.Input(
                x=ix,
                y=iy,
                jump=held.jump or latch.jump,
                jump_pressed=latch.jump,
                dash_pressed=latch.dash,
            )
            latch = Latch()
            prev_rect = p.body.rect
            p = player.step(p, inp, world, blocks, TICK)
            tick_no += 1
            look = blob.update_look(look, p, ix, iy, TICK)
            feet = Vec2(p.body.rect.center.x, p.body.rect.y + p.body.rect.h)
            puffs = blob.emit_puffs(puffs, p, feet, tick_no)
            puffs = blob.update_puffs(puffs, TICK)
            if "dash" in p.events:
                freeze = DASH_FREEZE
                shake = max(shake, 0.12)
                break
            if "land" in p.events and p.impact > 800:
                shake = max(shake, 0.06)
            if p.body.rect.y > world.rows * TILE + 64:
                p = player.spawn(start.x, start.y)
                prev_rect = p.body.rect

        alpha = 0.0 if freeze > 0 else acc / TICK
        draw_x = lerp(prev_rect.x, p.body.rect.x, alpha)
        draw_y = lerp(prev_rect.y, p.body.rect.y, alpha)
        center = Vec2(draw_x + p.body.rect.w / 2, draw_y + p.body.rect.h / 2)

        lead = Vec2(center.x + p.facing * 40 + p.vel.x * 0.08, center.y)
        cam = clamp_cam(follow(cam, lead, frame_dt), world, VIEW)
        shake = max(0.0, shake - frame_dt)
        jitter = 3.0 * shake / 0.12
        sx = math.sin(now * 91.0) * jitter
        sy = math.cos(now * 77.0) * jitter
        origin = Vec2(round(cam.x - VIEW.w / 2 + sx), round(cam.y - VIEW.h / 2 + sy))

        screen.fill((236, 120, 60))
        view = Rect(origin.x, origin.y, VIEW.w, VIEW.h)
        for cell in cells_overlapping(world, view):
            r = cell.rect
            cell.draw(screen, Rect(r.x - origin.x, r.y - origin.y, r.w, r.h))
        blob.draw_puffs(screen, puffs, origin)
        blob.draw_blob(
            screen,
            Vec2(center.x - origin.x, center.y - origin.y),
            look,
            dashes_left=p.dashes_left,
        )
        if show_debug:
            lines = (
                f"fps {clock.get_fps():5.1f}  vel {p.vel.x:6.0f},{p.vel.y:6.0f}",
                f"ground {p.on_ground} wall {p.wall_dir} slide {p.wall_sliding}",
                f"dash {p.dashing} left {p.dashes_left}  {sorted(p.events)}",
            )
            for i, line in enumerate(lines):
                screen.blit(font.render(line, True, (20, 20, 20)), (6, 6 + i * 14))
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
