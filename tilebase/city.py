"""Night-ruins chamber. The two crossing platforms start in the agent's pocket.

Run with `python -m tilebase.city`.

The room follows the cable-lift screen: a left arch, ice shelves, a spiked
alcove with the flag, and a stone bridge broken in two places. Enter a
prompt and the agent places the left or right platform from its pocket.
"""

from __future__ import annotations

import asyncio
import math

from tilebase.contraptions import Stock, place, stock_line
from tilebase.edit import Entities, define_entities
from tilebase.geom import Rect, Size, Vec2
from tilebase.kinds import hurt_at, level_tiles, overlaps_mark
from tilebase.play import (
    DASH_FREEZE,
    DASH_KEYS,
    JUMP_KEYS,
    TICK,
    WEB,
    Ground,
    Held,
    PLACE_DEADLINE,
    Latch,
    _codes,
    _frame_png,
    _ink,
    _same_words,
    axis,
    blocks,
    clamp_cam,
    follow,
    ground_effects,
    lerp,
    mend,
    read_held,
    ticks_for,
)
from tilebase.tiles import World, cells_overlapping, load_map

TILE = 32
# The whole room fits the window, the way the reference chamber is one screen.
VIEW = Size(30 * TILE, 17 * TILE)

# Glyphs from kinds: # stone  ~ ice  ^ spikes  E flag  S spawn
# Row 5 is the bridge, broken at columns 6 and 14. Each gap is one pocket platform.
#          012345678901234567890123456789
ROWS = (
    "..####......######..........#.",
    "..#..#......#^^^^#..........~.",
    "..#..#......#....#..........~.",
    "..#..#......#..E.#..........#.",
    "..####......................#.",
    "....##....####....####......#.",
    "....##......................#.",
    "....##~~~~............~~~~..#.",
    "....##~~~~............~~~~..##",
    "....##~~~~............~~~~....",
    "....##....................####",
    "...S..........................",
    "~~~~~~~~......................",
    "########..............########",
    "..............................",
    "..............................",
    "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^",
)

# Two crossings, spent when the agent places them.
POCKET: Stock = ("lift", "lift")


def world() -> World:
    rows = tuple(row.replace("S", ".") for row in ROWS)
    loaded = load_map(rows, level_tiles(), tile_size=TILE)
    if not isinstance(loaded, World):
        raise RuntimeError(loaded)
    return loaded


def exit_tiles() -> frozenset[tuple[int, int]]:
    found = {
        (col, row)
        for row, line in enumerate(ROWS)
        for col, glyph in enumerate(line)
        if glyph == "E"
    }
    return frozenset(found)


def open_room() -> tuple[World, Entities, Vec2]:
    """The chamber, with both platforms still in the pocket."""
    level = world()
    start = spawn_point()
    _level, entities = define_entities(
        level,
        (),
        bounds=Rect(0, 0, level.cols * TILE, level.rows * TILE),
        exit_tiles=exit_tiles(),
        spawn_rect=Rect(start.x, start.y, 22, 22),
    )
    return level, entities, start


def spawn_point(rows: tuple[str, ...] = ROWS) -> Vec2:
    for r, row in enumerate(rows):
        c = row.find("S")
        if c >= 0:
            return Vec2(c * TILE + (TILE - 22) / 2, r * TILE + TILE - 22)
    return Vec2(TILE, TILE)


def _sign(screen: object, origin: Vec2) -> None:
    import pygame

    x = round(3 * TILE + 4 - origin.x)
    y = round(1 * TILE + 6 - origin.y)
    pygame.draw.rect(screen, (232, 236, 226), (x, y, 52, 36))
    pygame.draw.rect(screen, (64, 140, 72), (x, y, 52, 36), 3)
    pygame.draw.line(screen, (64, 140, 72), (x + 8, y + 24), (x + 22, y + 14), 2)
    pygame.draw.line(screen, (64, 140, 72), (x + 22, y + 14), (x + 40, y + 20), 2)


def _snow_cap(screen: object, origin: Vec2) -> None:
    import pygame

    pygame.draw.circle(screen, (120, 190, 255), (round(28 * TILE + 10 - origin.x), round(36 - origin.y)), 26)
    pygame.draw.circle(screen, (186, 224, 255), (round(27 * TILE + 8 - origin.x), round(28 - origin.y)), 16)


def draw_hud(screen: object, line: str, stock: Stock) -> None:
    """Talk line on the left, pocket on the right. Bitmap glyphs, so it always shows."""
    import pygame

    top = VIEW.h - 28
    pygame.draw.rect(screen, (236, 224, 196), (0, top, VIEW.w, 28))
    _ink(screen, line, 8, top + 6, scale=2)
    label = stock_line(stock) or "pocket empty"
    _ink(screen, label, VIEW.w - 8 - 12 * len(label), top + 6, scale=2)


def draw_scene(
    screen: object,
    level: World,
    origin: Vec2,
    cleared: bool,
    line: str,
    stock: Stock,
) -> None:
    import pygame

    view = Rect(origin.x, origin.y, VIEW.w, VIEW.h)
    for cell in cells_overlapping(level, view):
        rect = cell.rect
        cell.draw(screen, Rect(rect.x - origin.x, rect.y - origin.y, rect.w, rect.h))
    _sign(screen, origin)
    _snow_cap(screen, origin)
    draw_hud(screen, line, stock)


def main() -> None:
    import os

    import pygame

    from tilebase.audio import Audio

    os.environ.setdefault("SDL_HINT_RENDER_VSYNC", "1")
    pygame.init()
    if WEB:
        screen = pygame.display.set_mode((VIEW.w, VIEW.h))
    else:
        screen = pygame.display.set_mode(
            (VIEW.w, VIEW.h), pygame.SCALED | pygame.RESIZABLE, vsync=1
        )
    pygame.display.set_caption("Grok the Gap — city")
    audio = Audio()
    audio.start()
    try:
        asyncio.run(run_level(screen, audio))
    finally:
        audio.stop()
        pygame.quit()


async def run_level(screen, audio=None) -> None:
    """Play the chamber. Enter asks the agent to place a pocket platform."""
    import pygame

    from tilebase import art, blob, player
    from tilebase.agent import AgentMiss, Placed, ask, level_grid, warm
    from tilebase.speech import ListenError, Transcript
    from tilebase.tiles import glyph_rows

    canvas = pygame.Surface((VIEW.w, VIEW.h)).convert()
    level, entities, start = open_room()
    jump_codes = _codes(pygame, JUMP_KEYS)
    dash_codes = _codes(pygame, DASH_KEYS)
    pad = None
    if pygame.joystick.get_count() > 0:
        pad = pygame.joystick.Joystick(0)

    def reset():
        room, held, spawn = open_room()
        return room, held, spawn, player.spawn(spawn.x, spawn.y), False, False, Ground()

    level, entities, start, p, cleared, edited, ground = reset()
    stock = POCKET
    prev_rect = p.body.rect
    look = blob.rest()
    puffs = blob.no_puffs()
    latch = Latch()
    acc = 0.0
    freeze = 0.0
    shake = 0.0
    tick_no = 0
    prompt = ""
    asking = False
    listening = False
    notice = "enter type    v talk"
    place_job: asyncio.Task[object] | None = None
    place_started = 0.0
    guess_job: asyncio.Task[object] | None = None
    guess_text = ""
    heard: asyncio.Queue[object] = asyncio.Queue()
    mic: asyncio.Task[None] | None = None
    asyncio.create_task(asyncio.to_thread(warm))
    cam = clamp_cam(p.body.rect.center, level, VIEW)
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
        grid = level_grid(
            glyph_rows(level), (int(center.x // TILE), int(center.y // TILE))
        )
        # The model takes coordinates from this list. These two holes are one lift each.
        grid += (
            "\n- open gap, place a lift here: cols 6-9, row 5"
            "\n- open gap, place a lift here: cols 14-17, row 5\n"
        )
        return asyncio.create_task(
            asyncio.to_thread(ask, text, _frame_png(canvas), stock, grid)
        )

    def guess(text: str) -> None:
        nonlocal guess_job, guess_text
        if place_job is not None or len(text.split()) < 3:
            return
        if _same_words(text, guess_text):
            return
        guess_text = text
        guess_job = start_ask(text)

    def submit(text: str) -> None:
        nonlocal notice, place_job, guess_job, guess_text, place_started
        if place_job is not None:
            return
        notice = "placing"
        place_started = pygame.time.get_ticks() / 1000.0
        if guess_job is not None and _same_words(text, guess_text):
            place_job = guess_job
        else:
            place_job = start_ask(text)
        guess_job = None
        guess_text = ""

    def finish_place(result: object) -> None:
        nonlocal level, stock, edited, notice
        if isinstance(result, Placed):
            placed = place(
                level, entities, stock, result.name, result.col, result.row, p.body.rect
            )
            if isinstance(placed, Refused):
                notice = placed.reason
            else:
                level = placed.world
                stock = placed.stock
                edited = True
                notice = f"{result.name} at {result.col},{result.row}"
        elif isinstance(result, AgentMiss):
            notice = result.message

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
                elif event.key == pygame.K_RETURN:
                    asking = True
                    prompt = ""
                elif event.key == pygame.K_v and not WEB and (mic is None or mic.done()):
                    listening = True
                    asking = True
                    prompt = ""
                    mic = asyncio.create_task(_hear())
                elif event.key == pygame.K_r:
                    level, entities, start, p, cleared, edited, ground = reset()
                    stock = POCKET
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

        while not heard.empty():
            heard_event = heard.get_nowait()
            if isinstance(heard_event, ListenError):
                listening = False
                asking = False
                notice = heard_event.message
            elif listening and isinstance(heard_event, Transcript):
                prompt = heard_event.text
                if not heard_event.final:
                    guess(prompt.strip())
                if heard_event.final:
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
            place_job = None
            notice = "model timed out"
        held_keys = read_held(pygame, pygame.key.get_pressed(), pad)
        if asking or place_job is not None:
            held_keys = Held(False, False, False, False, False, False)
            latch = Latch()
        ix = axis(held_keys.left, held_keys.right)
        iy = axis(held_keys.up, held_keys.down)

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
                jump=held_keys.jump or latch.jump,
                jump_pressed=latch.jump,
                dash_pressed=latch.dash,
            )
            latch = Latch()
            prev_rect = p.body.rect
            prev_vel = p.vel
            p = player.step(p, inp, level, blocks, TICK)
            p, level, ground = ground_effects(p, prev_vel, level, ground, TICK)
            tick_no += 1
            if audio is not None:
                audio.play_events(p.events, p.impact)
            look = blob.update_look(look, p, ix, iy, TICK)
            feet = Vec2(p.body.rect.center.x, p.body.rect.y + p.body.rect.h)
            puffs = blob.emit_puffs(puffs, p, feet, tick_no)
            puffs = blob.update_puffs(puffs, TICK)
            if edited and overlaps_mark(level, p.body.rect, "goal"):
                cleared = True
            if "dash" in p.events:
                freeze = DASH_FREEZE
                shake = max(shake, 0.12)
                break
            if "land" in p.events and p.impact > 800:
                shake = max(shake, 0.06)
            if hurt_at(level, p.body.rect) or p.body.rect.y > level.rows * TILE + 64:
                if audio is not None:
                    audio.play("death")
                    shake = max(shake, 0.2)
                p = player.spawn(start.x, start.y)
                prev_rect = p.body.rect
                level = mend(level, ground)
                ground = Ground()

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
        if cleared:
            line = "you made it"
        elif listening and not prompt:
            line = "listening"
        elif asking or listening:
            line = "> " + prompt + "_"
        else:
            line = notice
        art.draw_backdrop(canvas, cam, Size(level.cols * TILE, level.rows * TILE), VIEW)
        draw_scene(canvas, level, origin, cleared, line, stock)
        blob.draw_puffs(canvas, puffs, origin)
        art.draw_player(
            canvas,
            Vec2(center.x - origin.x, center.y - origin.y),
            p,
            look,
            dashes_left=p.dashes_left,
        )
        _present_level(screen, canvas)
        pygame.display.flip()
        if WEB:
            clock.tick(60)
        else:
            clock.tick(0 if _has_vsync(pygame) else 240)
        await asyncio.sleep(0)


def _present_level(screen, canvas) -> None:
    """Fit the whole chamber in the window the menu already opened."""
    import pygame

    sw, sh = screen.get_size()
    cw, ch = canvas.get_size()
    if (sw, sh) == (cw, ch):
        screen.blit(canvas, (0, 0))
        return
    scale = min(sw / cw, sh / ch)
    tw, th = max(1, round(cw * scale)), max(1, round(ch * scale))
    screen.fill((12, 16, 28))
    image = pygame.transform.smoothscale(canvas, (tw, th)) if scale < 1 else pygame.transform.scale(canvas, (tw, th))
    screen.blit(image, ((sw - tw) // 2, (sh - th) // 2))


def _has_vsync(pygame: object) -> bool:
    try:
        return pygame.display.is_vsync()
    except (AttributeError, pygame.error):
        return False


if __name__ == "__main__":
    main()
