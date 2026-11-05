"""Platformer controller for a round blob: pure, deterministic, tick-based.

Numbers follow Celeste scaled x4 (32px tiles vs 8px). Units are px and seconds.
`step` returns a new `Player`; nothing here touches pygame.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tilebase.geom import Rect, Vec2
from tilebase.move import Blocks, Body, move_body
from tilebase.tiles import World


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
    jump_cut: float = 0.5
    coyote_time: float = 0.1
    jump_buffer_time: float = 0.1
    wall_slide_max: float = 80.0
    wall_jump_reach: float = 12.0
    wall_jump_h: float = 520.0
    wall_jump_lock: float = 0.16


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
        dashes_left=0,
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
    vx, vy = p.vel.x, p.vel.y
    facing = inp.x if inp.x != 0 else p.facing
    force_time = max(0.0, p.force_time - dt)
    force_dir = p.force_dir if force_time > 0 else 0
    move_x = 0 if force_dir != 0 and inp.x == -force_dir else inp.x

    vx = _run(vx, move_x, grounded, t, dt)

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

    moved = move_body(world, p.body, Vec2(vx * dt, vy * dt), blocks)
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
        not on_ground and wall_dir != 0 and move_x == wall_dir and vy > 0
    )

    return replace(
        p,
        body=body,
        vel=Vec2(vx, vy),
        on_ground=on_ground,
        facing=facing,
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
