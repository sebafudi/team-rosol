"""Movement sandbox: fixed-step physics, event-driven input, smoothed camera.

Run with `python -m tilebase.play`. The map is a test bench for movement,
not a level.

Input latency budget: key events are drained right before each physics tick,
presses are latched as edges so a tap shorter than one tick still counts,
physics runs at 120 Hz, and the frame is drawn straight after the last tick.
"""

from __future__ import annotations

import asyncio
import math
import sys
from dataclasses import dataclass, replace

from tilebase.art import tile_drawer
from tilebase.credits import InsufficientCredits, charge, finite_ledger, grant
from tilebase.geom import Rect, Size, Vec2
from tilebase.kinds import blocks_cell, hurt_at, overlaps_mark, under_feet
from tilebase.move import Body
from tilebase.tiles import Cell, World, cells_overlapping, define, glyph_rows, load_map, put_cell
from tilebase.tokens import CounterLook, collect, counter_step, draw_balance

TILE = 32
# Two 10 s socket attempts plus slack. Past this, "placing" gives up.
PLACE_DEADLINE = 25.0
VIEW = Size(640, 360)
WINDOW_SCALE = 2
TICK = 1.0 / 120.0
WEB = sys.platform == "emscripten"
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
    "#######....###################################################",
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
    return blocks_cell(cell, body, delta)


# A spring throws you about five tiles up.
SPRING_SPEED = 1000.0
# On ice the run input only moves this share of the way toward its speed each tick.
ICE_GRIP = 0.15
# Cracked rock holds this long under your feet, then falls away.
CRUMBLE_DELAY = 0.4


@dataclass(frozen=True)
class Ground:
    """Cracked rock being stood on (seconds so far) and rock already fallen."""

    crumbling: tuple[tuple[tuple[int, int], float], ...] = ()
    broken: tuple[tuple[int, int], ...] = ()


def ground_effects(
    p: player.Player, prev_vel: Vec2, world: World, ground: Ground, dt: float
) -> tuple[player.Player, World, Ground]:
    """Ice keeps speed, springs launch, cracked rock falls after a short stand."""
    if not p.on_ground:
        return p, world, Ground(broken=ground.broken)
    cells = under_feet(world, p.body.rect)
    if any("slick" in cell.marks for cell in cells):
        vx = prev_vel.x + (p.vel.x - prev_vel.x) * ICE_GRIP
        p = replace(p, vel=Vec2(vx, p.vel.y))
    if any("bounce" in cell.marks for cell in cells):
        p = replace(p, vel=Vec2(p.vel.x, -SPRING_SPEED), on_ground=False)
    held = dict(ground.crumbling)
    timers: list[tuple[tuple[int, int], float]] = []
    broken = list(ground.broken)
    for cell in cells:
        if "crumble" not in cell.marks:
            continue
        key = (cell.col, cell.row)
        t = held.get(key, 0.0) + dt
        if t < CRUMBLE_DELAY:
            timers.append((key, t))
            continue
        put = put_cell(world, cell.col, cell.row, "empty")
        if isinstance(put, World):
            world = put
            broken.append(key)
    return p, world, Ground(tuple(timers), tuple(broken))


def mend(world: World, ground: Ground) -> World:
    """Put fallen cracked rock back, as on a respawn."""
    for col, row in ground.broken:
        put = put_cell(world, col, row, "crumble")
        if isinstance(put, World):
            world = put
    return world


def spawn_point(rows: tuple[str, ...]) -> Vec2:
    for r, row in enumerate(rows):
        c = row.find("S")
        if c >= 0:
            return Vec2(c * TILE + (TILE - 22) / 2, r * TILE + TILE - 22)
    return Vec2(TILE, TILE)


def _draw_empty(screen: object, rect: Rect) -> None:
    return None


def sandbox() -> World:
    loaded = load_map(
        tuple(row.replace("S", ".") for row in SANDBOX),
        (
            define(".", id="empty", draw=_draw_empty, marks=frozenset()),
            define("#", id="solid", draw=tile_drawer("solid"), marks=frozenset({"blocks"})),
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
    asyncio.run(run())


async def run() -> None:
    """The game loop yields each frame so the browser build can draw."""
    import os

    import pygame

    from tilebase import art, blob, player
    from tilebase.audio import Audio

    os.environ.setdefault("SDL_HINT_RENDER_VSYNC", "1")
    pygame.init()
    if WEB:
        screen = pygame.display.set_mode((VIEW.w, VIEW.h))
    else:
        screen = pygame.display.set_mode(
            (VIEW.w, VIEW.h), pygame.SCALED | pygame.RESIZABLE, vsync=1
        )
    pygame.display.set_caption("Grok the Gap")
    audio = Audio()
    audio.start()
    from tilebase.title import show

    choice = await show(screen, picker=True)
    if choice == "quit":
        audio.stop()
        pygame.quit()
        return
    if choice == "lifts":
        from tilebase.city import run_level

        await run_level(screen, audio)
        audio.stop()
        pygame.quit()
        return
    from tilebase.agent import AgentMiss, Placed, ask, level_grid, warm
    from tilebase.speech import ListenError, Transcript
    from tilebase.box import level_surface, open_level, overlaps_exit
    from tilebase.contraptions import Placement, place, stock_line

    priced = choice == "mint"
    if priced:
        from tilebase.mint import open_level
    level = open_level()
    world = level.world
    entities = level.entities
    stock = level.stock
    start = level.spawn
    prompt = ""
    asking = False
    listening = False
    place_job: asyncio.Task[object] | None = None
    place_started = 0.0
    # A call started on an interim transcript. If the final matches, it is used.
    guess_job: asyncio.Task[object] | None = None
    guess_text = ""
    asyncio.create_task(asyncio.to_thread(warm))
    heard: asyncio.Queue[object] = asyncio.Queue()
    mic: asyncio.Task[None] | None = None
    notice = "name a tile   enter   v talk"
    edited = False
    cleared = False
    ground = Ground()
    ledger = finite_ledger(0)
    counter = CounterLook()
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
    async def _hear() -> None:
        from tilebase.speech import listen

        async for event in listen():
            heard.put_nowait(event)
            if isinstance(event, ListenError):
                return
            if isinstance(event, Transcript) and event.final:
                return

    def start_ask(text: str) -> asyncio.Task[object]:
        center = Vec2(
            p.body.rect.x + p.body.rect.w / 2,
            p.body.rect.y + p.body.rect.h / 2,
        )
        sheet = level_surface(world, center, p, look, p.dashes_left)
        grid = level_grid(
            glyph_rows(world), (int(center.x // TILE), int(center.y // TILE))
        )
        return asyncio.create_task(
            asyncio.to_thread(ask, text, _frame_png(sheet), stock, grid)
        )

    def guess(text: str) -> None:
        nonlocal guess_job, guess_text
        if place_job is not None or len(text.split()) < 3:
            return
        if _same_words(text, guess_text):
            return
        guess_text = text
        guess_job = start_ask(text)

    def can_prompt() -> bool:
        nonlocal notice
        if priced and not ledger.balance:
            notice = "no tokens   collect o to prompt"
            return False
        return True

    def submit(text: str) -> None:
        nonlocal notice, place_job, guess_job, guess_text, ledger, place_started
        if place_job is not None:
            return
        if priced:
            paid = charge(ledger, 1, reason="prompt", stage="place")
            if isinstance(paid, InsufficientCredits):
                can_prompt()
                return
            ledger = paid.ledger
        notice = "placing"
        place_started = pygame.time.get_ticks() / 1000.0
        if guess_job is not None and _same_words(text, guess_text):
            place_job = guess_job
        else:
            place_job = start_ask(text)
        guess_job = None
        guess_text = ""

    def finish_place(result: object) -> None:
        nonlocal world, stock, edited, notice, ledger
        if isinstance(result, Placed):
            placed = place(
                world, entities, stock, result.name, result.col, result.row, p.body.rect
            )
            if isinstance(placed, Placement):
                world = placed.world
                stock = placed.stock
                edited = True
                notice = f"{result.name} at {result.col},{result.row}"
                return
            notice = placed.reason
        elif isinstance(result, AgentMiss):
            notice = result.message
        if priced:
            ledger = grant(ledger, 1, reason="refund")


    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and listening:
                if event.key == pygame.K_ESCAPE:
                    listening = False
                    asking = False
                    if mic is not None and not mic.done():
                        mic.cancel()
            elif event.type == pygame.KEYDOWN and asking:
                if event.key == pygame.K_ESCAPE:
                    asking = False
                elif event.key == pygame.K_RETURN:
                    text = prompt.strip()
                    prompt = ""
                    asking = False
                    if text:
                        submit(text)
                elif event.key == pygame.K_BACKSPACE:
                    prompt = prompt[:-1]
                elif event.unicode.isprintable():
                    prompt += event.unicode
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN and can_prompt():
                    asking = True
                    prompt = ""
                elif event.key == pygame.K_v and not WEB and (mic is None or mic.done()) and can_prompt():
                    listening = True
                    asking = True
                    prompt = ""
                    mic = asyncio.create_task(_hear())
                elif event.key == pygame.K_r:
                    p = player.spawn(start.x, start.y)
                    prev_rect = p.body.rect
                elif event.key == pygame.K_F1:
                    show_debug = not show_debug
                elif event.key == pygame.K_m:
                    audio.toggle_music()
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

        while not heard.empty():
            event = heard.get_nowait()
            if isinstance(event, ListenError):
                listening = False
                asking = False
                notice = event.message
            elif listening and isinstance(event, Transcript):
                prompt = event.text
                if not event.final:
                    guess(prompt.strip())
                if event.final:
                    listening = False
                    asking = False
                    text = prompt.strip()
                    prompt = ""
                    if text:
                        submit(text)
        now = pygame.time.get_ticks() / 1000.0
        frame_dt = now - last
        last = now
        if place_job is not None and place_job.done():
            job, place_job = place_job, None
            error = job.exception()
            finish_place(AgentMiss(f"model failed: {error}") if error else job.result())
        elif place_job is not None and now - place_started > PLACE_DEADLINE:
            # The thread keeps running, but its answer is dropped.
            place_job = None
            notice = "model timed out"
        held = read_held(pygame, pygame.key.get_pressed(), pad)
        if asking or place_job is not None:
            held = Held(False, False, False, False, False, False)
            latch = Latch()
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
            prev_vel = p.vel
            p = player.step(p, inp, world, blocks, TICK)
            p, world, ground = ground_effects(p, prev_vel, world, ground, TICK)
            tick_no += 1
            audio.play_events(p.events, p.impact)
            look = blob.update_look(look, p, ix, iy, TICK)
            feet = Vec2(p.body.rect.center.x, p.body.rect.y + p.body.rect.h)
            puffs = blob.emit_puffs(puffs, p, feet, tick_no)
            puffs = blob.update_puffs(puffs, TICK)
            world, ledger, gained = collect(world, p.body.rect, ledger)
            if gained:
                audio.play("collect")
            if "dash" in p.events:
                freeze = DASH_FREEZE
                shake = max(shake, 0.12)
                break
            if "land" in p.events and p.impact > 800:
                shake = max(shake, 0.06)
            # Spikes and lava kill on contact. Below the map is the same respawn.
            if hurt_at(world, p.body.rect) or p.body.rect.y > world.rows * TILE + 64:
                audio.play("death")
                shake = max(shake, 0.2)
                p = player.spawn(start.x, start.y)
                prev_rect = p.body.rect
                world = mend(world, ground)
                ground = Ground()
            elif edited and (
                overlaps_mark(world, p.body.rect, "goal")
                or overlaps_exit(p.body.rect, entities)
            ):
                cleared = True

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

        art.draw_backdrop(
            screen, cam, Size(world.cols * TILE, world.rows * TILE), VIEW
        )
        view = Rect(origin.x, origin.y, VIEW.w, VIEW.h)
        for cell in cells_overlapping(world, view):
            r = cell.rect
            cell.draw(screen, Rect(r.x - origin.x, r.y - origin.y, r.w, r.h))
        blob.draw_puffs(screen, puffs, origin)
        art.draw_player(
            screen,
            Vec2(center.x - origin.x, center.y - origin.y),
            p,
            look,
            dashes_left=p.dashes_left,
        )
        counter = counter_step(counter, ledger.balance, frame_dt)
        draw_balance(screen, ledger.balance, VIEW.w, counter)
        if cleared:
            line = "you made it"
        elif listening and not prompt:
            line = "listening"
        elif asking or listening:
            line = "> " + prompt + "_"
        else:
            line = notice
        _bar(screen, line, stock_line(stock))
        if show_debug:
            rows = (
                f"fps {clock.get_fps():5.1f}  vel {p.vel.x:6.0f},{p.vel.y:6.0f}",
                f"ground {p.on_ground} wall {p.wall_dir} slide {p.wall_sliding}",
                f"dash {p.dashing} left {p.dashes_left}  {sorted(p.events)}",
            )
            for i, row in enumerate(rows):
                _ink(screen, row, 6, 6 + i * 10, scale=1)
        pygame.display.flip()
        if WEB:
            clock.tick(60)
        else:
            clock.tick(0 if _has_vsync(pygame) else 240)
        await asyncio.sleep(0)
    if mic is not None and not mic.done():
        mic.cancel()
    audio.stop()
    pygame.quit()


_GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("10001", "10001", "10001", "11111", "00001", "00001", "00001"),
    "5": ("11111", "10000", "10000", "11110", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ">": ("10000", "01000", "00100", "00010", "00100", "01000", "10000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00110", "01100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
}


def _ink(screen: object, message: str, x: int, y: int, scale: int) -> None:
    import pygame

    cursor = x
    for character in message.upper():
        glyph = _GLYPHS.get(character, _GLYPHS[" "])
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit == "1":
                    pygame.draw.rect(
                        screen,
                        (28, 24, 22),
                        (cursor + col * scale, y + row * scale, scale, scale),
                    )
        cursor += 6 * scale


def _same_words(a: str, b: str) -> bool:
    """Interim and final transcripts differ in case and punctuation only."""

    def words(text: str) -> list[str]:
        return "".join(c.lower() if c.isalnum() else " " for c in text).split()

    return bool(a) and words(a) == words(b)


def _frame_png(screen: object) -> bytes:
    """The pixels on screen right now, before the placing notice covers them."""
    import struct
    import zlib

    import pygame

    width, height = screen.get_size()
    rgb = pygame.image.tobytes(screen, "RGB")
    rows = b"".join(
        b"\x00" + rgb[y * width * 3 : (y + 1) * width * 3] for y in range(height)
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows, 6))
        + chunk(b"IEND", b"")
    )


def _bar(screen: object, line: str, stock: str) -> None:
    import pygame

    pygame.draw.rect(screen, (236, 224, 196), (0, 332, 640, 28))
    _ink(screen, line, 8, 338, scale=2)
    if stock:
        _ink(screen, stock, 640 - 8 - 6 * len(stock), 342, scale=1)


def _has_vsync(pygame: object) -> bool:
    try:
        return pygame.display.is_vsync()
    except (AttributeError, pygame.error):
        return False


if __name__ == "__main__":
    main()
