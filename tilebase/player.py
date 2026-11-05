"""Platformer controller for a round blob: pure, deterministic, tick-based.

Numbers follow Celeste scaled x4 (32px tiles vs 8px). Units are px and seconds.
`step` returns a new `Player`; nothing here touches pygame.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tilebase.geom import Rect, Vec2
from tilebase.move import Blocks, Body, Moved, move_body
from tilebase.tiles import World, cells_overlapping


@dataclass(frozen=True)
class Input:
    x: int
    y: int
    jump: bool
    jump_pressed: bool
    dash_pressed: bool


@dataclass(frozen=True)
class Tuning:
    width: float = 22.0
    height: float = 22.0
    max_run: float = 360.0
    run_accel: float = 4000.0
    run_decel: float = 1600.0
    air_mult: float = 0.65
    gravity: float = 3600.0
    max_fall: float = 640.0
    fast_max_fall: float = 960.0
    half_grav_threshold: float = 160.0
    jump_speed: float = 420.0
    jump_h_boost: float = 160.0
    var_jump_time: float = 0.18
    jump_cut: float = 1.0
    coyote_time: float = 0.1
    jump_buffer_time: float = 0.1
    wall_slide_max: float = 80.0
    wall_jump_reach: float = 12.0
    wall_jump_h: float = 520.0
    wall_jump_lock: float = 0.16
    dashes: int = 1
    dash_speed: float = 960.0
    dash_time: float = 0.15
    dash_end_speed: float = 640.0
    dash_up_mult: float = 0.75
    dash_buffer_time: float = 0.08
    corner_correction: float = 10.0
    ledge_pop: float = 8.0
    edge_support: float = 0.35
    edge_nudge_speed: float = 120.0
    hard_landing: float = 700.0


@dataclass(frozen=True)
class Player:
    body: Body
    vel: Vec2
    on_ground: bool
    facing: int
    wall_dir: int
    wall_sliding: bool
    dashing: bool
    dashes_left: int
    events: frozenset[str]
    impact: float
    coyote: float = 0.0
    jump_buffer: float = 0.0
    var_jump: float = 0.0
    var_jump_speed: float = 0.0
    force_time: float = 0.0
    force_dir: int = 0
    dash_buffer: float = 0.0
    dash_time: float = 0.0
    dash_dir: Vec2 = Vec2(0.0, 0.0)
    nudging: bool = False


def spawn(x: float, y: float, tuning: Tuning = Tuning()) -> Player:
    """`x`, `y` is the top-left of the hitbox."""
    return Player(
        body=Body(Rect(x, y, tuning.width, tuning.height)),
        vel=Vec2(0.0, 0.0),
        on_ground=False,
        facing=1,
        wall_dir=0,
        wall_sliding=False,
        dashing=False,
        dashes_left=tuning.dashes,
        events=frozenset(),
        impact=0.0,
    )


def step(
    p: Player,
    inp: Input,
    world: World,
    blocks: Blocks,
    dt: float,
    tuning: Tuning = Tuning(),
) -> Player:
    t = tuning
    events: set[str] = set()
    grounded = _touching(world, p.body, 0, 1, blocks) and p.vel.y >= 0

    coyote = t.coyote_time if grounded else max(0.0, p.coyote - dt)
    jump_buffer = (
        t.jump_buffer_time if inp.jump_pressed else max(0.0, p.jump_buffer - dt)
    )
    var_jump = max(0.0, p.var_jump - dt)
    var_jump_speed = p.var_jump_speed
    dash_buffer = (
        t.dash_buffer_time if inp.dash_pressed else max(0.0, p.dash_buffer - dt)
    )
    vx, vy = p.vel.x, p.vel.y
    facing = p.facing if p.dashing or inp.x == 0 else inp.x
    force_time = max(0.0, p.force_time - dt)
    force_dir = p.force_dir if force_time > 0 else 0
    move_x = 0 if force_dir != 0 and inp.x == -force_dir else inp.x
    dashing, dash_dir, dashes_left = p.dashing, p.dash_dir, p.dashes_left
    dash_time = max(0.0, p.dash_time - dt)
    nudging = False

    if dashing and dash_time <= 1e-9:
        dashing = False
        events.add("dash_end")
        if vx * dash_dir.x + vy * dash_dir.y > t.dash_end_speed:
            vx, vy = dash_dir.x * t.dash_end_speed, dash_dir.y * t.dash_end_speed
            if vy < 0:
                vy *= t.dash_up_mult

    if not dashing and dash_buffer > 0 and dashes_left > 0:
        dash_dir = _dash_dir(inp, facing)
        vx, vy = dash_dir.x * t.dash_speed, dash_dir.y * t.dash_speed
        dashing, dash_time = True, t.dash_time
        dashes_left -= 1
        dash_buffer, var_jump, force_time, force_dir = 0.0, 0.0, 0.0, 0
        facing = _sign(dash_dir.x) or facing
        events.add("dash")
    elif dashing:
        if jump_buffer > 0 and grounded and dash_dir.y >= 0 and dash_dir.x != 0:
            # Dash-jump: keep the dash's horizontal speed (a Celeste "super").
            dashing = False
            dashes_left = t.dashes
            vy = -t.jump_speed
            var_jump, var_jump_speed = t.var_jump_time, vy
            jump_buffer, coyote, grounded = 0.0, 0.0, False
            events.update(("dash_end", "jump"))
    else:
        # A hard landing while steering keeps all momentum: the ball rolls on.
        hard_landing = (
            "land" in p.events and p.impact > t.hard_landing and inp.x != 0
        )
        if not hard_landing:
            vx = _run(vx, move_x, grounded, t, dt)
        if grounded and inp.x == 0:
            roll = _edge_roll(world, p.body, t.edge_support, blocks)
            if roll != 0:
                nudging = True
                if _sign(vx) != roll or abs(vx) < t.edge_nudge_speed:
                    vx = roll * t.edge_nudge_speed
                if not p.nudging:
                    events.add("edge_nudge")
        if jump_buffer > 0 and (grounded or coyote > 0):
            vy = -t.jump_speed
            vx += t.jump_h_boost * inp.x
            var_jump, var_jump_speed = t.var_jump_time, vy
            jump_buffer, coyote, grounded = 0.0, 0.0, False
            events.add("jump")
        elif jump_buffer > 0 and not grounded:
            wall = _wall_near(world, p.body, t.wall_jump_reach, inp.x, blocks)
            if wall != 0:
                away = -wall
                vx, vy = t.wall_jump_h * away, -t.jump_speed
                var_jump, var_jump_speed = t.var_jump_time, vy
                force_time, force_dir = t.wall_jump_lock, away
                facing = away
                jump_buffer = 0.0
                events.add("wall_jump")

        sliding = (
            not grounded and p.wall_dir != 0 and move_x == p.wall_dir and vy >= 0
        )
        if not grounded:
            vy = _fall(vy, inp, t, dt, t.wall_slide_max if sliding else None)
            if var_jump > 0:
                if inp.jump:
                    vy = min(vy, var_jump_speed)
                else:
                    var_jump = 0.0
                    if vy < 0:
                        vy *= t.jump_cut

    delta = Vec2(vx * dt, vy * dt)
    moved = move_body(world, p.body, delta, blocks)
    if moved.blocked_y and vy < 0:
        moved = _slip_corner(world, p.body, delta, t.corner_correction, blocks) or moved
    if moved.blocked_x and vx != 0 and (dashing or not grounded):
        moved = _pop_ledge(world, p.body, delta, t.ledge_pop, blocks) or moved
    body = moved.body
    fall_speed = vy
    if moved.blocked_x:
        vx = 0.0
    if moved.blocked_y:
        if vy < 0:
            events.add("bonk")
            var_jump = 0.0
        vy = 0.0

    on_ground = vy >= 0 and _touching(world, body, 0, 1, blocks)
    impact = 0.0
    if on_ground and not p.on_ground:
        events.add("land")
        impact = max(0.0, fall_speed)
    if p.on_ground and not on_ground:
        events.add("leave_ground")
    wall_dir = _wall_near(world, body, 1.0, move_x, blocks)
    if wall_dir != 0 and p.wall_dir == 0:
        events.add("wall_touch")
    wall_sliding = (
        not on_ground
        and not dashing
        and wall_dir != 0
        and move_x == wall_dir
        and vy > 0
    )
    if on_ground and not dashing:
        dashes_left = t.dashes

    return replace(
        p,
        body=body,
        vel=Vec2(vx, vy),
        on_ground=on_ground,
        facing=facing,
        dashing=dashing,
        dashes_left=dashes_left,
        wall_dir=wall_dir,
        wall_sliding=wall_sliding,
        events=frozenset(events),
        impact=impact,
        coyote=coyote,
        jump_buffer=jump_buffer,
        var_jump=var_jump,
        var_jump_speed=var_jump_speed,
        force_time=force_time,
        force_dir=force_dir,
        dash_buffer=dash_buffer,
        dash_time=dash_time,
        dash_dir=dash_dir,
        nudging=nudging,
    )


def _run(vx: float, x: int, grounded: bool, t: Tuning, dt: float) -> float:
    mult = 1.0 if grounded else t.air_mult
    if x != 0 and abs(vx) > t.max_run and _sign(vx) == x:
        return _approach(vx, t.max_run * x, t.run_decel * mult * dt)
    if x != 0:
        return _approach(vx, t.max_run * x, t.run_accel * mult * dt)
    return _approach(vx, 0.0, t.run_decel * mult * dt)


def _fall(
    vy: float, inp: Input, t: Tuning, dt: float, slide_cap: float | None
) -> float:
    """Gravity and the fall cap in one approach: below the cap it accelerates,
    above it (letting go of fast-fall, grabbing a wall) it eases back down."""
    mult = 0.5 if abs(vy) < t.half_grav_threshold and inp.jump else 1.0
    cap = t.fast_max_fall if inp.y == 1 else t.max_fall
    if slide_cap is not None:
        cap = slide_cap
    return _approach(vy, cap, t.gravity * mult * dt)


def _dash_dir(inp: Input, facing: int) -> Vec2:
    if inp.x == 0 and inp.y == 0:
        return Vec2(float(facing), 0.0)
    if inp.x != 0 and inp.y != 0:
        diag = 0.5**0.5
        return Vec2(inp.x * diag, inp.y * diag)
    return Vec2(float(inp.x), float(inp.y))


def _slip_corner(
    world: World, body: Body, delta: Vec2, reach: float, blocks: Blocks
) -> Moved | None:
    """Head clipped a ceiling corner: shift sideways (toward travel first) to clear it."""
    first = _sign(delta.x) or 1
    for offset in range(1, int(reach) + 1):
        for side in (first, -first):
            shifted = move_body(world, body, Vec2(side * offset, 0), blocks)
            if shifted.blocked_x:
                continue
            moved = move_body(world, shifted.body, delta, blocks)
            if not moved.blocked_y:
                return moved
    return None


def _pop_ledge(
    world: World, body: Body, delta: Vec2, reach: float, blocks: Blocks
) -> Moved | None:
    """Blocked by a lip at most `reach` px tall: the round body rolls up onto it."""
    for lift in range(1, int(reach) + 1):
        lifted = move_body(world, body, Vec2(0, -lift), blocks)
        if lifted.blocked_y:
            return None
        across = move_body(world, lifted.body, Vec2(delta.x, 0), blocks)
        if not across.blocked_x:
            down = move_body(world, across.body, Vec2(0, delta.y), blocks)
            return Moved(down.body, False, down.blocked_y)
    return None


def _edge_roll(world: World, body: Body, min_support: float, blocks: Blocks) -> int:
    """Direction to roll off a ledge when too little of the body is supported."""
    r = body.rect
    feet = Rect(r.x, r.y + r.h, r.w, 1.0)
    spans = [
        (max(r.x, c.rect.x), min(r.x + r.w, c.rect.x + c.rect.w))
        for c in cells_overlapping(world, feet)
        if blocks(c, body, Vec2(0.0, 1.0))
    ]
    support = sum(hi - lo for lo, hi in spans)
    if support <= 0 or support >= min_support * r.w:
        return 0
    middle = sum((lo + hi) / 2 * (hi - lo) for lo, hi in spans) / support
    return 1 if r.center.x > middle else -1


def _wall_near(
    world: World, body: Body, reach: float, prefer: int, blocks: Blocks
) -> int:
    """Side (-1/1) of a wall within `reach` px, 0 if none. Ties go to `prefer`."""
    sides = (prefer, -prefer) if prefer != 0 else (1, -1)
    for side in sides:
        if move_body(world, body, Vec2(side * reach, 0), blocks).blocked_x:
            return side
    return 0


def _touching(world: World, body: Body, dx: float, dy: float, blocks: Blocks) -> bool:
    moved = move_body(world, body, Vec2(dx, dy), blocks)
    return moved.blocked_x or moved.blocked_y


def _approach(value: float, target: float, amount: float) -> float:
    if value < target:
        return min(value + amount, target)
    return max(value - amount, target)


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)
