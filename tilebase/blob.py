"""Placeholder character art: a white jelly ball with two orange pill eyes.

Everything here is cosmetic. `update_look` turns physics state into animation
state (springs, blinks, eye gaze, roll); `draw_blob` paints it with pygame
primitives. Puffs are tiny dust particles spawned from physics events.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Protocol

from tilebase.geom import Vec2

RADIUS = 13.0
SS = 4  # supersample factor for smooth edges on a tiny screen

BODY = (246, 244, 238)
BODY_SPENT = (178, 204, 236)
SHADE = (206, 200, 196)
SHADE_SPENT = (132, 160, 204)
RIM = (60, 46, 52)
EYE = (214, 92, 22)
SEAM = (222, 216, 210)
SEAM_SPENT = (156, 184, 222)

# Spring: underdamped so impulses overshoot once (jelly), settling in ~0.25s.
OMEGA = 30.0
ZETA = 0.42
MAX_STEP = 1.0 / 240.0


class PlayerLike(Protocol):
    @property
    def vel(self) -> Vec2: ...
    @property
    def on_ground(self) -> bool: ...
    @property
    def facing(self) -> int: ...
    @property
    def wall_dir(self) -> int: ...
    @property
    def wall_sliding(self) -> bool: ...
    @property
    def dashing(self) -> bool: ...
    @property
    def events(self) -> frozenset[str]: ...
    @property
    def impact(self) -> float: ...


@dataclass(frozen=True)
class Look:
    sx: float = 1.0  # body scale along the draw axis (x, or dash direction)
    sy: float = 1.0
    vsx: float = 0.0  # spring velocities
    vsy: float = 0.0
    lean: float = 0.0  # px shift of the body, e.g. pressed into a wall
    vlean: float = 0.0
    angle: float = 0.0  # radians; body axis rotation (only while dashing)
    eye_x: float = 0.0  # gaze offset in px
    eye_y: float = 0.0
    face: float = 1.0  # smoothed facing, -1..1; mirrors the eye placement
    eye_open: float = 1.0  # eye height factor (wide > 1 > squint)
    squint: float = 0.0  # seconds of squint left
    blink_in: float = 2.5  # seconds until next blink
    blink: float = 0.0  # seconds of current blink left
    blinks: int = 0
    breathe: float = 0.0  # phase, radians
    still: float = 0.0  # 0..1 how much breathing shows
    roll: float = 0.0  # radians, for the surface mark
    time: float = 0.0


BLINK_TIME = 0.13


def rest() -> Look:
    return Look()


def _next_blink(count: int) -> float:
    return 2.0 + 3.0 * random.Random(count * 7919 + 17).random()


def _approach(value: float, target: float, rate: float, dt: float) -> float:
    return value + (target - value) * (1.0 - math.exp(-rate * dt))


def _spring(x: float, v: float, target: float, dt: float) -> tuple[float, float]:
    steps = max(1, math.ceil(dt / MAX_STEP))
    h = dt / steps
    for _ in range(steps):
        v += (-OMEGA * OMEGA * (x - target) - 2.0 * ZETA * OMEGA * v) * h
        x += v * h
    return x, v


def _squash(look: Look, sx: float, sy: float) -> Look:
    """Kick the springs to a deformed shape; they wobble back on their own."""
    return replace(look, sx=sx, sy=sy, vsx=0.0, vsy=0.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def update_look(look: Look, player: PlayerLike, input_x: int, input_y: int, dt: float) -> Look:
    events = player.events
    vx, vy = player.vel.x, player.vel.y
    squint = max(0.0, look.squint - dt)

    # Event impulses: set the deformation, let the springs do the rest.
    if "land" in events:
        a = _clamp(player.impact / 960.0, 0.0, 1.0)
        look = _squash(look, 1.0 + 0.12 + 0.38 * a, 1.0 - 0.1 - 0.32 * a)
        if player.impact > 520.0:
            squint = 0.2
    if "jump" in events or "wall_jump" in events:
        look = _squash(look, 0.72, 1.34)
    if "bonk" in events:
        look = _squash(look, 1.3, 0.72)
    if "wall_touch" in events:
        look = replace(_squash(look, 0.72, 1.22), lean=player.wall_dir * 2.5)
    if "dash" in events:
        look = _squash(look, 1.5, 0.66)

    # Continuous targets.
    tx, ty, tlean = 1.0, 1.0, 0.0
    if player.dashing:
        tx, ty = 1.32, 0.76
    elif player.wall_sliding:
        tx, ty, tlean = 0.86, 1.1, player.wall_dir * 1.5
    elif not player.on_ground:
        s = _clamp(abs(vy) / 960.0, 0.0, 1.0) * 0.14
        tx, ty = 1.0 - s, 1.0 + s

    sx, vsx = _spring(look.sx, look.vsx, tx, dt)
    sy, vsy = _spring(look.sy, look.vsy, ty, dt)
    lean, vlean = _spring(look.lean, look.vlean, tlean, dt)

    angle = math.atan2(vy, vx) if player.dashing and (vx or vy) else 0.0

    # Eyes look where you steer, else where you move.
    gx = float(input_x) if input_x else _clamp(vx / 360.0, -1.0, 1.0)
    gy = float(input_y) if input_y else _clamp(vy / 700.0, -1.0, 1.0)
    eye_x = _approach(look.eye_x, gx * 1.6, 22.0, dt)
    eye_y = _approach(look.eye_y, gy * 1.4, 22.0, dt)
    face = _approach(look.face, float(player.facing or 1), 18.0, dt)

    target_open = 1.0
    if squint > 0.0:
        target_open = 0.45
    elif vy > 560.0 and not player.on_ground:
        target_open = 1.0 + 0.25 * _clamp((vy - 560.0) / 400.0, 0.0, 1.0)
    eye_open = _approach(look.eye_open, target_open, 30.0, dt)

    blink_in = look.blink_in - dt
    blink = max(0.0, look.blink - dt)
    blinks = look.blinks
    if blink_in <= 0.0:
        blinks += 1
        blink = BLINK_TIME
        blink_in += _next_blink(blinks)

    calm = player.on_ground and abs(vx) < 20.0 and not player.dashing
    still = _approach(look.still, 1.0 if calm else 0.0, 4.0, dt)
    breathe = (look.breathe + dt * math.tau / 2.6) % math.tau
    roll = (look.roll + vx * dt / RADIUS) % math.tau

    return Look(
        sx=sx, sy=sy, vsx=vsx, vsy=vsy, lean=lean, vlean=vlean, angle=angle,
        eye_x=eye_x, eye_y=eye_y, face=face, eye_open=eye_open, squint=squint,
        blink_in=blink_in, blink=blink, blinks=blinks,
        breathe=breathe, still=still, roll=roll, time=look.time + dt,
    )


def blink_amount(look: Look) -> float:
    """0 = eyes open, 1 = fully shut."""
    if look.blink <= 0.0:
        return 0.0
    t = 1.0 - look.blink / BLINK_TIME
    return 1.0 - abs(2.0 * t - 1.0)


def _body_scale(look: Look) -> tuple[float, float]:
    b = math.sin(look.breathe) * 0.03 * look.still
    return look.sx * (1.0 - b * 0.6), look.sy * (1.0 + b)


def draw_blob(screen: object, center: Vec2, look: Look, *, dashes_left: int) -> None:
    import pygame

    spent = dashes_left <= 0
    body = BODY_SPENT if spent else BODY
    shade = SHADE_SPENT if spent else SHADE
    seam = SEAM_SPENT if spent else SEAM

    sx, sy = _body_scale(look)
    r = RADIUS * SS
    w = max(2, round(2 * r * sx))
    h = max(2, round(2 * r * sy))

    # Body on its own layer so it can be rotated along a dash.
    pad = 2 * SS
    layer = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    outer = pygame.Rect(pad, pad, w, h)
    pygame.draw.ellipse(layer, RIM, outer)
    rim = SS
    inner = outer.inflate(-2 * rim, -2 * rim)
    pygame.draw.ellipse(layer, shade, inner)
    # Lit area: a slightly smaller ellipse shifted up-left leaves a soft shadow crescent.
    lit = inner.inflate(-round(w * 0.12), -round(h * 0.12))
    lit.move_ip(-round(w * 0.05), -round(h * 0.07))
    pygame.draw.ellipse(layer, body, lit.clip(inner))
    # Rolling mark: a faint dot on the surface that travels with distance.
    mx = outer.centerx + math.cos(look.roll - math.pi / 2) * w * 0.33
    my = outer.centery + math.sin(look.roll - math.pi / 2) * h * 0.33
    pygame.draw.circle(layer, seam, (mx, my), 1.3 * SS)

    if look.angle:
        layer = pygame.transform.rotate(layer, -math.degrees(look.angle))

    size = round((RADIUS * 2 * 1.7 + 8) * SS)
    canvas = pygame.Surface((size, size), pygame.SRCALPHA)
    cx = size / 2 + look.lean * SS
    cy = size / 2 + (1.0 - sy) * r  # keep the bottom planted when squashing
    canvas.blit(layer, layer.get_rect(center=(round(cx), round(cy))))

    # Eyes stay upright; they ride the squash using the axis-aligned scale.
    ex_scale = sx if not look.angle else math.sqrt(sx * sy)
    ey_scale = sy if not look.angle else math.sqrt(sx * sy)
    open_h = look.eye_open * (1.0 - blink_amount(look))
    eye_w = 2.9 * SS * ex_scale
    eye_h = max(0.9 * SS, 7.0 * SS * ey_scale * open_h)
    for base_x in (1.8, 6.9):
        ex = cx + (base_x * look.face + look.eye_x) * SS * ex_scale
        ey = cy + (-3.2 + look.eye_y) * SS * ey_scale
        rect = pygame.Rect(0, 0, round(eye_w), round(eye_h))
        rect.center = (round(ex), round(ey))
        pygame.draw.rect(canvas, EYE, rect, border_radius=round(min(eye_w, eye_h) / 2))

    small = pygame.transform.smoothscale(canvas, (size // SS, size // SS))
    screen.blit(small, small.get_rect(center=(round(center.x), round(center.y))))


# --- Dust puffs -------------------------------------------------------------

PUFF = (238, 232, 224)
MAX_PUFFS = 48


@dataclass(frozen=True)
class Puff:
    pos: Vec2  # world px
    vel: Vec2
    age: float
    life: float
    size: float  # final radius in px


@dataclass(frozen=True)
class Puffs:
    items: tuple[Puff, ...] = ()


def no_puffs() -> Puffs:
    return Puffs()


def _spray(
    rng: random.Random, origin: Vec2, count: int, base: Vec2, spread: Vec2, size: float, life: float
) -> list[Puff]:
    out = []
    for _ in range(count):
        out.append(
            Puff(
                pos=Vec2(origin.x + rng.uniform(-2.0, 2.0), origin.y + rng.uniform(-1.0, 1.0)),
                vel=Vec2(base.x + rng.uniform(-spread.x, spread.x), base.y + rng.uniform(-spread.y, spread.y)),
                age=0.0,
                life=life * rng.uniform(0.8, 1.2),
                size=size * rng.uniform(0.7, 1.2),
            )
        )
    return out


def emit_puffs(puffs: Puffs, player: PlayerLike, feet: Vec2, seed: int) -> Puffs:
    """Spawn dust for this frame's events. `feet` is the bottom-center in world px."""
    events = player.events
    if not events:
        return puffs
    rng = random.Random(seed)
    new: list[Puff] = []
    if "land" in events:
        a = _clamp(player.impact / 960.0, 0.0, 1.0)
        n = 2 + round(4 * a)
        speed = 40.0 + 90.0 * a
        for side in (-1.0, 1.0):
            new += _spray(rng, Vec2(feet.x + side * 6.0, feet.y), n, Vec2(side * speed, -12.0), Vec2(20.0, 8.0), 2.0 + 2.0 * a, 0.3)
    if "jump" in events:
        for side in (-1.0, 1.0):
            new += _spray(rng, Vec2(feet.x + side * 7.0, feet.y), 2, Vec2(side * 45.0, 6.0), Vec2(15.0, 8.0), 2.2, 0.25)
    if "wall_jump" in events:
        side = float(player.wall_dir) or -float(player.facing or 1)
        wall = Vec2(feet.x + side * 13.0, feet.y - 8.0)
        new += _spray(rng, wall, 4, Vec2(side * 8.0, 10.0), Vec2(8.0, 40.0), 2.6, 0.3)
    if "dash" in events:
        vx, vy = player.vel.x, player.vel.y
        n = math.hypot(vx, vy) or 1.0
        bx, by = -vx / n, -vy / n
        tail = Vec2(feet.x + bx * RADIUS, feet.y - RADIUS + by * RADIUS)
        new += _spray(rng, tail, 5, Vec2(bx * 70.0, by * 70.0), Vec2(25.0, 25.0), 3.0, 0.32)
    return Puffs((puffs.items + tuple(new))[-MAX_PUFFS:])


def update_puffs(puffs: Puffs, dt: float) -> Puffs:
    drag = math.exp(-6.0 * dt)
    out = []
    for p in puffs.items:
        age = p.age + dt
        if age >= p.life:
            continue
        out.append(
            Puff(
                pos=Vec2(p.pos.x + p.vel.x * dt, p.pos.y + p.vel.y * dt),
                vel=Vec2(p.vel.x * drag, p.vel.y * drag - 20.0 * dt),
                age=age,
                life=p.life,
                size=p.size,
            )
        )
    return Puffs(tuple(out))


def draw_puffs(screen: object, puffs: Puffs, offset: Vec2) -> None:
    import pygame

    for p in puffs.items:
        t = p.age / p.life
        r = p.size * (0.4 + 0.6 * math.sqrt(t))
        alpha = round(200 * (1.0 - t) ** 1.5)
        if alpha <= 0 or r < 0.5:
            continue
        d = math.ceil(r * 2) + 2
        dot = pygame.Surface((d, d), pygame.SRCALPHA)
        pygame.draw.circle(dot, (*PUFF, alpha), (d / 2, d / 2), r)
        screen.blit(dot, (round(p.pos.x - offset.x - d / 2), round(p.pos.y - offset.y - d / 2)))
