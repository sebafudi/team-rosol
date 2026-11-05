# Named Map-Object Edit API

A structured, safe layer above raw `put_cell` for editing named entities in the tile world.

## Overview

The edit API lets you define named entities (platforms, doors, gates) and apply structured commands (move, place, remove, toggle) with automatic safety checks. All edits return new immutable worlds, preserving the functional style of the existing codebase.

## Quick Start

```python
from tilebase.edit import Entity, Command, apply_edit, define_entities
from tilebase.geom import Rect

# 1. Define named entities
world, entities = define_entities(
    world,
    (
        Entity(id="plat1", type="platform", tiles=((5, 8), (6, 8), (7, 8))),
        Entity(id="door1", type="door", tiles=((10, 5),), open=False),
    ),
    bounds=Rect(0, 0, 640, 320),  # Allowed edit area
    exit_tiles=frozenset({(18, 5)}),  # Protected exit
    spawn_rect=Rect(32, 200, 12, 14),  # Player spawn area
)

# 2. Apply a move command
result = apply_edit(
    world,
    entities,
    Command(op="move", id="plat1", by=(0, -2))  # Move up 2 tiles
)

# 3. Handle the result
if isinstance(result, EditSuccess):
    new_world = result.world
    new_entities = result.entities
    print(f"Changed {len(result.changed_tiles)} tiles")
else:
    print(f"Edit rejected: {type(result).__name__}")
```

## Entity Types

- **platform**: Solid blocks that can be moved
- **door**: Toggleable barriers (open/closed)
- **gate**: Similar to doors

Each entity has:
- `id`: Unique identifier (string)
- `type`: Entity type (string)
- `tiles`: Tuple of `(col, row)` positions
- `open`: Boolean for toggleable types (default `False`)

## Commands

All commands use the `Command(op, id, ...)` structure:

### Move
```python
Command(op="move", id="plat1", by=(dx, dy))
```
Shifts an entity by `(dx, dy)` tiles. Old tiles are cleared, new tiles are filled.

### Place
```python
Command(op="place", id="new_plat", tiles=((5, 3), (6, 3)))
```
Creates a new platform entity at the specified tiles.

### Remove
```python
Command(op="remove", id="plat1")
```
Deletes an entity, clearing its tiles to empty.

### Toggle
```python
Command(op="toggle", id="door1")
```
Flips a door/gate between open (empty tile) and closed (solid tile).

## Safety Checks

All edits are validated before application:

1. **Bounds check**: Edits outside `bounds` are rejected (`OutOfBounds`)
2. **Exit protection**: Blocking `exit_tiles` is rejected (`ExitBlocked`)
3. **Spawn protection**: Overlapping `spawn_rect` is rejected (`PlayerBuried`)
4. **Entity existence**: Unknown `id` returns `UnknownEntity`
5. **Operation validity**: Unknown `op` returns `UnknownOp`

## Result Types

### Success
- `EditSuccess(world, entities, changed_tiles)`: New world + entities, plus tiles that were modified

### Errors
- `UnknownOp(op)`: Invalid operation name
- `UnknownEntity(id)`: Entity not found
- `OutOfBounds(tiles)`: Edit extends beyond allowed bounds
- `ExitBlocked(tiles)`: Would block protected exit tiles
- `PlayerBuried(tiles)`: Would overlap player spawn area
- `InvalidOperation(reason)`: Other validation failure

## Demo

Run the included demo to see a complete example:

```bash
python3 -m tilebase.edit_demo
```

The demo creates a world with two platforms, moves one up by 2 tiles, verifies collision detection, and tests safety rejection.

## Integration Notes

- Works with existing `World` and `put_cell` from `tiles.py`
- Returns new immutable worlds (no in-place mutation)
- Follows frozen dataclass pattern used throughout the codebase
- Designed for AI prompt → structured command → safe execution flow
