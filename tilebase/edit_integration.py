"""Integration patterns for using the edit API in a live game.

Shows how to wire structured edits into a game loop, track pending changes,
and handle visual feedback for edited tiles. Designed for AI-driven prompts
that translate to Command objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from tilebase.edit import Command, EditResult, EditSuccess, Entities
from tilebase.geom import Rect
from tilebase.tiles import World


@dataclass(frozen=True)
class PendingEdit:
    """An edit queued for application, with optional preview/feedback."""

    command: Command
    preview: bool = False


@dataclass(frozen=True)
class EditState:
    """Game state tracking edits and their visual feedback."""

    world: World
    entities: Entities
    pending: tuple[PendingEdit, ...]
    highlight_tiles: frozenset[tuple[int, int]]
    highlight_frames: int


def create_edit_state(world: World, entities: Entities) -> EditState:
    """Initialize edit state for a game session."""
    return EditState(
        world=world,
        entities=entities,
        pending=(),
        highlight_tiles=frozenset(),
        highlight_frames=0,
    )


def queue_edit(state: EditState, command: Command, *, preview: bool = False) -> EditState:
    """Add an edit to the pending queue. Set preview=True to show before applying."""
    from dataclasses import replace

    edit = PendingEdit(command=command, preview=preview)
    return replace(state, pending=state.pending + (edit,))


def apply_pending_edits(state: EditState) -> tuple[EditState, tuple[EditResult, ...]]:
    """Apply all pending edits and return results + updated state with highlights."""
    from dataclasses import replace
    from tilebase.edit import apply_edit

    world = state.world
    entities = state.entities
    results = []
    all_changed: set[tuple[int, int]] = set()

    for edit in state.pending:
        result = apply_edit(world, entities, edit.command)
        results.append(result)
        if isinstance(result, EditSuccess):
            world = result.world
            entities = result.entities
            all_changed.update(result.changed_tiles)
        else:
            break

    return (
        replace(
            state,
            world=world,
            entities=entities,
            pending=(),
            highlight_tiles=frozenset(all_changed),
            highlight_frames=60,
        ),
        tuple(results),
    )


def update_highlights(state: EditState) -> EditState:
    """Decay highlight timer each frame. Call once per frame."""
    from dataclasses import replace

    if state.highlight_frames <= 0:
        return replace(state, highlight_tiles=frozenset(), highlight_frames=0)
    frames = state.highlight_frames - 1
    tiles = frozenset() if frames <= 0 else state.highlight_tiles
    return replace(state, highlight_tiles=tiles, highlight_frames=frames)


def tile_rects(
    tiles: frozenset[tuple[int, int]], tile_size: int
) -> tuple[Rect, ...]:
    """Convert tile positions to world rects for rendering highlights."""
    return tuple(
        Rect(col * tile_size, row * tile_size, tile_size, tile_size)
        for col, row in tiles
    )


def prompt_to_command(prompt: str, entities: Entities) -> Command | None:
    """Stub: convert natural language to Command. Replace with actual parser/LLM."""
    prompt = prompt.lower().strip()

    if "raise" in prompt and "left" in prompt:
        from tilebase.edit import entities_by_type

        platforms = entities_by_type(entities, "platform")
        if platforms:
            left = min(platforms, key=lambda p: min(c for c, r in p.tiles))
            return Command(op="move", id=left.id, by=(0, -1))

    if "lower" in prompt and "right" in prompt:
        from tilebase.edit import entities_by_type

        platforms = entities_by_type(entities, "platform")
        if platforms:
            right = max(platforms, key=lambda p: max(c for c, r in p.tiles))
            return Command(op="move", id=right.id, by=(0, 1))

    if "open" in prompt and "door" in prompt:
        from tilebase.edit import entities_by_type

        doors = entities_by_type(entities, "door")
        if doors:
            return Command(op="toggle", id=doors[0].id)

    return None
