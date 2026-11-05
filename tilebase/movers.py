"""Cable lifts: solid platforms that travel a vertical track when stood on.

A lift waits at `home`. Landing on it sends it to `goal`, holds, then returns.
The rider is carried. Nothing here touches pygame.
"""

from __future__ import annotations

from dataclasses import replace

from tilebase.geom import Rect, Vec2
from tilebase.move import Blocks, Body, move_body
from tilebase.player import Input, Player, step
from tilebase.tiles import World


class Mover:
    __slots__ = (
        "id",
        "x",
        "y",
        "w",
        "h",
        "home",
        "goal",
        "pulley",
        "speed",
        "phase",
        "hold",
        "pause",
    )

    def __init__(
        self,
        id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        home: float,
        goal: float,
        pulley: float,
        speed: float = 220.0,
        phase: str = "wait",
        hold: float = 0.0,
        pause: float = 0.75,
    ) -> None:
        self.id = id
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.home = home
        self.goal = goal
        self.pulley = pulley
        self.speed = speed
        self.phase = phase
        self.hold = hold
        self.pause = pause

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.w, self.h)

    def clone(self, **changes: float | str) -> Mover:
        nxt = Mover(
            self.id,
            self.x,
            self.y,
            self.w,
            self.h,
            self.home,
            self.goal,
            self.pulley,
            self.speed,
            self.phase,
            self.hold,
            self.pause,
        )
        for key, value in changes.items():
            setattr(nxt, key, value)
        return nxt


def step_mover(mover: Mover, dt: float, ridden: bool) -> Mover:
    """Advance one lift. `ridden` only departs a lift that is waiting at home."""
    if mover.phase == "wait":
        if ridden and abs(mover.y - mover.home) <= 0.5:
            return mover.clone(phase="up")
        return mover
    if mover.phase == "up":
        y = mover.y - mover.speed * dt
        if y <= mover.goal:
            return mover.clone(y=mover.goal, phase="hold", hold=mover.pause)
        return mover.clone(y=y)
    if mover.phase == "hold":
        hold = mover.hold - dt
        if hold <= 0.0:
            return mover.clone(hold=0.0, phase="down")
        return mover.clone(hold=hold)
    y = mover.y + mover.speed * dt
    if y >= mover.home:
        return mover.clone(y=mover.home, phase="wait", hold=0.0)
    return mover.clone(y=y)


def ridden(body: Body, movers: tuple[Mover, ...]) -> Mover | None:
    """The lift whose top the body is standing on, if the overlap is real."""
    rect = body.rect
    feet = rect.y + rect.h
    best: Mover | None = None
    best_overlap = 4.0
    for mover in movers:
        overlap = min(rect.x + rect.w, mover.x + mover.w) - max(rect.x, mover.x)
        if overlap > best_overlap and abs(feet - mover.y) <= 2.0:
            best = mover
            best_overlap = overlap
    return best


def ride_step(
    player: Player,
    movers: tuple[Mover, ...],
    world: World,
    blocks: Blocks,
    inp: Input,
    dt: float,
) -> tuple[Player, tuple[Mover, ...]]:
    """Physics tick: collide with the lifts, then carry whoever is standing on one."""
    solids = tuple(mover.rect for mover in movers)
    player = step(player, inp, world, blocks, dt, extras=solids)
    ride = ridden(player.body, movers)
    movers = tuple(
        step_mover(mover, dt, ride is not None and mover.id == ride.id) for mover in movers
    )
    if ride is None:
        return player, movers
    moved = next(mover for mover in movers if mover.id == ride.id)
    target_y = moved.y - player.body.rect.h
    dy = target_y - player.body.rect.y
    others = tuple(mover.rect for mover in movers if mover.id != moved.id)
    carried = move_body(world, player.body, Vec2(0.0, dy), blocks, others)
    feet = carried.body.rect.y + carried.body.rect.h
    if abs(feet - moved.y) <= 2.0:
        player = replace(player, body=carried.body, vel=Vec2(player.vel.x, 0.0), on_ground=True)
    else:
        player = replace(player, body=carried.body)
    return player, movers
