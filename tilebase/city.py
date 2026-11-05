"""Night-ruins chamber. The two crossing platforms start in the agent's pocket.

Run with `python -m tilebase.city`.

The room follows the cable-lift screen: a left arch, ice shelves, a spiked
alcove with the flag, and a stone bridge broken in two places. Enter a
prompt and the agent places the left or right platform from its pocket.
"""

from __future__ import annotations

import asyncio
import math

from tilebase.edit import Command, EditSuccess, Entities, apply_edit, define_entities, find_entity
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
    Latch,
    _codes,
    _frame_png,
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

# The two platforms the agent is holding. Each covers four tiles.
SLOTS = ("left", "right")
SPAN = 4


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


def platform_tiles(col: int, row: int) -> tuple[tuple[int, int], ...]:
    return tuple((col + dx, row) for dx in range(SPAN))


def place_platform(world: World, entities: Entities, slot: str, col: int, row: int):
    """Put one pocket platform. Placing the same slot again moves it."""
    if slot not in SLOTS:
        from tilebase.edit import InvalidOperation

        return InvalidOperation(f"unknown platform {slot}")
    tiles = platform_tiles(col, row)
    current = find_entity(entities, slot)
    if current is None:
        return apply_edit(world, entities, Command(op="place", id=slot, tiles=tiles))
    origin_col = min(c for c, _r in current.tiles)
    origin_row = min(r for _c, r in current.tiles)
    return apply_edit(
        world,
        entities,
        Command(op="move", id=slot, by=(col - origin_col, row - origin_row)),
    )


def pocket_slots(entities: Entities) -> tuple[str, ...]:
    """Platforms the agent is still holding."""
    return tuple(slot for slot in SLOTS if find_entity(entities, slot) is None)


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


def draw_platforms(screen: object, entities: Entities, origin: Vec2) -> None:
    """Grey bars for platforms that have left the pocket."""
    import pygame

    for slot in SLOTS:
        entity = find_entity(entities, slot)
        if entity is None:
            continue
        for col, row in entity.tiles:
            x = round(col * TILE - origin.x)
            y = round(row * TILE - origin.y)
            pygame.draw.rect(screen, (72, 80, 92), (x, y, TILE, TILE))
            pygame.draw.rect(screen, (176, 186, 198), (x + 4, y + 6, TILE - 8, TILE - 12))
            pygame.draw.circle(screen, (90, 98, 110), (x + TILE // 2, y + TILE // 2), 6, 2)


def draw_pocket(screen: object, entities: Entities) -> None:
    """The platforms the agent is still holding, along the bottom left."""
    import pygame

    holding = pocket_slots(entities)
    for index, slot in enumerate(SLOTS):
        x = 12 + index * 150
        y = VIEW.h - 46
        held = slot in holding
        pygame.draw.rect(screen, (16, 20, 32), (x, y, 136, 28))
        color = (176, 186, 198) if held else (60, 66, 76)
        pygame.draw.rect(screen, color, (x + 8, y + 8, 72, 12))
        pygame.draw.circle(screen, (40, 28, 24), (x + 44, y + 14), 3)
        try:
            font = pygame.font.Font(None, 18)
        except (NotImplementedError, pygame.error):
            font = None
        if font is not None:
            label = slot if held else "placed"
            text = font.render(label, True, (230, 236, 244))
            screen.blit(text, (x + 86, y + 7))


def draw_scene(
    screen: object,
    level: World,
    entities: Entities,
    origin: Vec2,
    cleared: bool,
    line: str,
) -> None:
    import pygame

    view = Rect(origin.x, origin.y, VIEW.w, VIEW.h)
    for cell in cells_overlapping(level, view):
        rect = cell.rect
        cell.draw(screen, Rect(rect.x - origin.x, rect.y - origin.y, rect.w, rect.h))
    _sign(screen, origin)
    _snow_cap(screen, origin)
    draw_platforms(screen, entities, origin)
    draw_pocket(screen, entities)
    bar = pygame.Rect(0, VIEW.h - 22, VIEW.w, 22)
    pygame.draw.rect(screen, (236, 224, 196), bar)
    try:
        font = pygame.font.Font(None, 22)
    except (NotImplementedError, pygame.error):
        font = None
    if font is not None:
        screen.blit(font.render(line, True, (28, 24, 22)), (8, VIEW.h - 20))
    if cleared:
        banner = pygame.Rect(VIEW.w // 2 - 130, 16, 260, 28)
        pygame.draw.rect(screen, (16, 24, 48), banner)
        pygame.draw.rect(screen, (180, 210, 255), banner, 2)
        try:
            font = pygame.font.Font(None, 22)
        except (NotImplementedError, pygame.error):
            font = None
        if font is not None:
            text = font.render("Flag reached", True, (220, 235, 255))
            screen.blit(text, text.get_rect(center=banner.center))


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
    from tilebase.agent import AgentMiss, PlacedPlatform, ask_platforms

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
    notice = "enter places a platform"
    place_job: asyncio.Task[object] | None = None
    cam = clamp_cam(p.body.rect.center, level, VIEW)
    clock = pygame.time.Clock()
    last = pygame.time.get_ticks() / 1000.0

    def submit(text: str) -> None:
        nonlocal notice, place_job
        if place_job is not None:
            return
        frame = _frame_png(canvas)
        notice = "placing a platform"
        place_job = asyncio.create_task(asyncio.to_thread(ask_platforms, text, frame))

    def finish_place(result: object) -> None:
        nonlocal level, entities, edited, notice
        if isinstance(result, PlacedPlatform):
            edit = place_platform(level, entities, result.slot, result.col, result.row)
            if isinstance(edit, EditSuccess):
                level = edit.world
                entities = edit.entities
                edited = True
                notice = f"{result.slot} at {result.col},{result.row}"
            else:
                notice = type(edit).__name__
        elif isinstance(result, AgentMiss):
            notice = result.message

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
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
                elif event.key == pygame.K_r:
                    level, entities, start, p, cleared, edited, ground = reset()
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
        if place_job is not None and place_job.done():
            result = place_job.result()
            place_job = None
            finish_place(result)
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
        elif asking:
            line = "> " + prompt + "_"
        else:
            line = notice
        art.draw_backdrop(canvas, cam, Size(level.cols * TILE, level.rows * TILE), VIEW)
        draw_scene(canvas, level, entities, origin, cleared, line)
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
