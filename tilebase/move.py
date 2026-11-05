from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tilebase.geom import Rect, Vec2
from tilebase.tiles import Cell, World, cells_overlapping


@dataclass(frozen=True)
class Body:
    rect: Rect


@dataclass(frozen=True)
class Keys:
    left: bool
    right: bool
    up: bool
    down: bool
    action: bool


@dataclass(frozen=True)
class Frame:
    keys: Keys
    dt: float
    body: Body
    world: World


PlanMove = Callable[[Frame], Vec2]


@dataclass(frozen=True)
class Moved:
    body: Body
    blocked_x: bool
    blocked_y: bool


Blocks = Callable[[Cell, Body, Vec2], bool]


def move_body(world: World, body: Body, delta: Vec2, blocks: Blocks) -> Moved:
    """Move on X, then Y. `body` passed to `blocks` is the pose before that step.

    Each step is at most one tile wide so a one-tile wall cannot be skipped.
    """
    rect, blocked_x = _move_axis(world, body, delta.x, axis="x", blocks=blocks)
    rect, blocked_y = _move_axis(world, Body(rect), delta.y, axis="y", blocks=blocks)
    return Moved(Body(rect), blocked_x, blocked_y)


def _move_axis(
    world: World,
    body: Body,
    amount: float,
    *,
    axis: str,
    blocks: Blocks,
) -> tuple[Rect, bool]:
    if amount == 0:
        return body.rect, False
    remaining = amount
    rect = body.rect
    blocked = False
    limit = float(world.tile_size)
    while abs(remaining) > 1e-9:
        step = max(-limit, min(limit, remaining))
        before = Body(rect)
        rect = _shift(rect, step if axis == "x" else 0.0, step if axis == "y" else 0.0)
        probe = Vec2(step, 0.0) if axis == "x" else Vec2(0.0, step)
        hits = tuple(
            cell
            for cell in cells_overlapping(world, rect)
            if blocks(cell, before, probe)
        )
        remaining -= step
        if not hits:
            continue
        blocked = True
        rect = _flush(rect, hits, axis=axis, direction=step)
        break
    return rect, blocked


def _shift(rect: Rect, dx: float, dy: float) -> Rect:
    return Rect(rect.x + dx, rect.y + dy, rect.w, rect.h)


def _flush(rect: Rect, hits: tuple[Cell, ...], *, axis: str, direction: float) -> Rect:
    if axis == "x" and direction > 0:
        edge = min(cell.rect.x for cell in hits)
        return Rect(edge - rect.w, rect.y, rect.w, rect.h)
    if axis == "x":
        edge = max(cell.rect.x + cell.rect.w for cell in hits)
        return Rect(edge, rect.y, rect.w, rect.h)
    if direction > 0:
        edge = min(cell.rect.y for cell in hits)
        return Rect(rect.x, edge - rect.h, rect.w, rect.h)
    edge = max(cell.rect.y + cell.rect.h for cell in hits)
    return Rect(rect.x, edge, rect.w, rect.h)
