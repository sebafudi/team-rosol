"""Named map-object editing API for structured, safe level mutations.

Provides a layer above raw `put_cell` that lets prompts like "raise the left
platform" become safe structured commands against named entities. Each entity
has an id, type, footprint (tile positions), and type-specific marks. Edits
are constrained to an allowed bounds and reject unsafe operations (deleting
the exit, burying the player, unknown entities).

Example:
    world, entities = define_entities(
        world,
        (
            Entity(id="plat1", type="platform", tiles=((5, 8), (6, 8), (7, 8))),
            Entity(id="door1", type="door", tiles=((10, 5),), open=False),
        ),
        bounds=Rect(2, 2, 16, 10),
    )
    result = apply_edit(world, entities, Command(op="move", id="plat1", by=(0, -2)))
    if isinstance(result, EditSuccess):
        new_world, new_entities = result.world, result.entities
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tilebase.geom import Rect
from tilebase.tiles import World, put_cell


@dataclass(frozen=True)
class Entity:
    """A named editable object in the world."""

    id: str
    type: str
    tiles: tuple[tuple[int, int], ...]
    open: bool = False


@dataclass(frozen=True)
class Entities:
    """Collection of named entities plus edit constraints."""

    items: tuple[Entity, ...]
    bounds: Rect
    exit_tiles: frozenset[tuple[int, int]]
    spawn_rect: Rect | None


@dataclass(frozen=True)
class Command:
    """Structured edit operation: move, place, remove, or toggle."""

    op: str
    id: str
    by: tuple[int, int] = (0, 0)
    tiles: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class EditSuccess:
    world: World
    entities: Entities
    changed_tiles: frozenset[tuple[int, int]]


@dataclass(frozen=True)
class UnknownOp:
    op: str


@dataclass(frozen=True)
class UnknownEntity:
    id: str


@dataclass(frozen=True)
class OutOfBounds:
    tiles: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ExitBlocked:
    tiles: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PlayerBuried:
    tiles: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class InvalidOperation:
    reason: str


EditResult = (
    EditSuccess
    | UnknownOp
    | UnknownEntity
    | OutOfBounds
    | ExitBlocked
    | PlayerBuried
    | InvalidOperation
)


def define_entities(
    world: World,
    items: tuple[Entity, ...],
    *,
    bounds: Rect,
    exit_tiles: frozenset[tuple[int, int]] = frozenset(),
    spawn_rect: Rect | None = None,
) -> tuple[World, Entities]:
    """Create an Entities collection. World is unchanged."""
    return world, Entities(items, bounds, exit_tiles, spawn_rect)


def apply_edit(world: World, entities: Entities, cmd: Command) -> EditResult:
    """Apply a structured edit command and return a new world + entities."""
    if cmd.op == "move":
        return _apply_move(world, entities, cmd)
    elif cmd.op == "remove":
        return _apply_remove(world, entities, cmd)
    elif cmd.op == "place":
        return _apply_place(world, entities, cmd)
    elif cmd.op == "toggle":
        return _apply_toggle(world, entities, cmd)
    return UnknownOp(cmd.op)


def _apply_move(world: World, entities: Entities, cmd: Command) -> EditResult:
    entity = _find_entity(entities, cmd.id)
    if entity is None:
        return UnknownEntity(cmd.id)

    new_tiles = tuple((c + cmd.by[0], r + cmd.by[1]) for c, r in entity.tiles)
    if not _tiles_in_bounds(new_tiles, entities.bounds, world):
        return OutOfBounds(new_tiles)

    old_tile_id = _tile_id_for_type(entity.type, entity.open)
    clear_world = _clear_tiles(world, entity.tiles, "empty")
    if isinstance(clear_world, World):
        fill_world = _fill_tiles(clear_world, new_tiles, old_tile_id)
        if isinstance(fill_world, World):
            new_entity = replace(entity, tiles=new_tiles)
            new_entities = _replace_entity(entities, new_entity)
            if not _safe_result(fill_world, new_entities, new_tiles):
                return _safety_error(fill_world, new_entities, new_tiles)
            changed = frozenset(entity.tiles) | frozenset(new_tiles)
            return EditSuccess(fill_world, new_entities, changed)
    return InvalidOperation("move failed to update world tiles")


def _apply_remove(world: World, entities: Entities, cmd: Command) -> EditResult:
    entity = _find_entity(entities, cmd.id)
    if entity is None:
        return UnknownEntity(cmd.id)

    clear_world = _clear_tiles(world, entity.tiles, "empty")
    if isinstance(clear_world, World):
        new_entities = replace(
            entities, items=tuple(e for e in entities.items if e.id != cmd.id)
        )
        if not _safe_result(clear_world, new_entities, entity.tiles):
            return _safety_error(clear_world, new_entities, entity.tiles)
        return EditSuccess(clear_world, new_entities, frozenset(entity.tiles))
    return InvalidOperation("remove failed to clear tiles")


def _apply_place(world: World, entities: Entities, cmd: Command) -> EditResult:
    if not cmd.tiles:
        return InvalidOperation("place requires tiles")
    entity = _find_entity(entities, cmd.id)
    if entity is not None:
        return InvalidOperation(f"entity {cmd.id} already exists")

    if not _tiles_in_bounds(cmd.tiles, entities.bounds, world):
        return OutOfBounds(cmd.tiles)

    tile_id = _tile_id_for_type("platform", False)
    fill_world = _fill_tiles(world, cmd.tiles, tile_id)
    if isinstance(fill_world, World):
        new_entity = Entity(id=cmd.id, type="platform", tiles=cmd.tiles)
        new_entities = replace(
            entities, items=entities.items + (new_entity,)
        )
        if not _safe_result(fill_world, new_entities, cmd.tiles):
            return _safety_error(fill_world, new_entities, cmd.tiles)
        return EditSuccess(fill_world, new_entities, frozenset(cmd.tiles))
    return InvalidOperation("place failed to fill tiles")


def _apply_toggle(world: World, entities: Entities, cmd: Command) -> EditResult:
    entity = _find_entity(entities, cmd.id)
    if entity is None:
        return UnknownEntity(cmd.id)
    if entity.type not in ("door", "gate"):
        return InvalidOperation(f"cannot toggle {entity.type}")

    new_open = not entity.open
    tile_id = _tile_id_for_type(entity.type, new_open)
    fill_world = _fill_tiles(world, entity.tiles, tile_id)
    if isinstance(fill_world, World):
        new_entity = replace(entity, open=new_open)
        new_entities = _replace_entity(entities, new_entity)
        if not _safe_result(fill_world, new_entities, entity.tiles):
            return _safety_error(fill_world, new_entities, entity.tiles)
        return EditSuccess(fill_world, new_entities, frozenset(entity.tiles))
    return InvalidOperation("toggle failed to update tiles")


def _find_entity(entities: Entities, entity_id: str) -> Entity | None:
    return next((e for e in entities.items if e.id == entity_id), None)


def _replace_entity(entities: Entities, new_entity: Entity) -> Entities:
    items = tuple(
        new_entity if e.id == new_entity.id else e for e in entities.items
    )
    return replace(entities, items=items)


def _tiles_in_bounds(
    tiles: tuple[tuple[int, int], ...], bounds: Rect, world: World
) -> bool:
    for col, row in tiles:
        x = col * world.tile_size
        y = row * world.tile_size
        if not (
            bounds.x <= x < bounds.x + bounds.w
            and bounds.y <= y < bounds.y + bounds.h
        ):
            return False
        if not (0 <= col < world.cols and 0 <= row < world.rows):
            return False
    return True


def _clear_tiles(
    world: World, tiles: tuple[tuple[int, int], ...], fill_id: str
) -> World:
    for col, row in tiles:
        result = put_cell(world, col, row, fill_id)
        if not isinstance(result, World):
            return world
        world = result
    return world


def _fill_tiles(
    world: World, tiles: tuple[tuple[int, int], ...], tile_id: str
) -> World:
    for col, row in tiles:
        result = put_cell(world, col, row, tile_id)
        if not isinstance(result, World):
            return world
        world = result
    return world


def _tile_id_for_type(entity_type: str, open: bool) -> str:
    if entity_type == "platform":
        return "solid"
    if entity_type == "door":
        return "empty" if open else "solid"
    if entity_type == "gate":
        return "empty" if open else "solid"
    return "solid"


def _safe_result(
    world: World, entities: Entities, changed: tuple[tuple[int, int], ...]
) -> bool:
    if entities.exit_tiles:
        entity_tiles = frozenset(
            tile for e in entities.items for tile in e.tiles if not e.open
        )
        if entities.exit_tiles & entity_tiles:
            return False

    if entities.spawn_rect:
        entity_tiles = frozenset(
            tile for e in entities.items for tile in e.tiles if not e.open
        )
        for col, row in entity_tiles:
            tile_rect = Rect(
                col * world.tile_size,
                row * world.tile_size,
                world.tile_size,
                world.tile_size,
            )
            if _rects_overlap(entities.spawn_rect, tile_rect):
                return False
    return True


def _safety_error(
    world: World, entities: Entities, changed: tuple[tuple[int, int], ...]
) -> EditResult:
    if entities.exit_tiles:
        entity_tiles = frozenset(
            tile for e in entities.items for tile in e.tiles if not e.open
        )
        blocked = entities.exit_tiles & entity_tiles
        if blocked:
            return ExitBlocked(tuple(blocked))

    if entities.spawn_rect:
        entity_tiles = frozenset(
            tile for e in entities.items for tile in e.tiles if not e.open
        )
        buried = []
        for col, row in entity_tiles:
            tile_rect = Rect(
                col * world.tile_size,
                row * world.tile_size,
                world.tile_size,
                world.tile_size,
            )
            if _rects_overlap(entities.spawn_rect, tile_rect):
                buried.append((col, row))
        if buried:
            return PlayerBuried(tuple(buried))
    return InvalidOperation("safety check failed")


def _rects_overlap(a: Rect, b: Rect) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    )
