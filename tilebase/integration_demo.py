"""Demo of edit API integration patterns.

Run with: python3 -m tilebase.integration_demo

Shows how to queue edits, apply them with highlights, and use prompt_to_command
for simple natural language → structured edit translation.
"""

from tilebase.art import tile_drawer
from tilebase.geom import Rect
from tilebase.tiles import World, define, load_map

from tilebase.edit import Entity, define_entities
from tilebase.edit_integration import (
    apply_pending_edits,
    create_edit_state,
    prompt_to_command,
    queue_edit,
    tile_rects,
    update_highlights,
)


TILE = 32

DEMO_MAP = (
    "####################",
    "#..................#",
    "#..................#",
    "#..................#",
    "#...####.......##..#",
    "#..................#",
    "#..................#",
    "####################",
)


def _draw_empty(screen: object, rect: Rect) -> None:
    return None


def print_world_section(world: World, row_start: int, row_count: int) -> None:
    from tilebase.tiles import _cell

    for r in range(row_start, min(row_start + row_count, world.rows)):
        line = ""
        for c in range(world.cols):
            cell = _cell(world, c, r)
            line += "#" if "blocks" in cell.marks else "."
        print(f"  {line}")


def demo() -> None:
    print("=== Edit Integration Demo ===\n")

    loaded = load_map(
        DEMO_MAP,
        (
            define(".", id="empty", draw=_draw_empty, marks=frozenset()),
            define(
                "#",
                id="solid",
                draw=tile_drawer("solid"),
                marks=frozenset({"blocks"}),
            ),
        ),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    world = loaded

    world, entities = define_entities(
        world,
        (
            Entity(id="plat_left", type="platform", tiles=((4, 4), (5, 4), (6, 4), (7, 4))),
            Entity(id="plat_right", type="platform", tiles=((15, 4), (16, 4))),
        ),
        bounds=Rect(0, 0, 20 * TILE, 8 * TILE),
    )

    state = create_edit_state(world, entities)

    print("1. Initial state (rows 3-6):")
    print_world_section(state.world, 3, 4)
    print()

    print("2. Process natural language prompts\n")
    prompts = [
        "raise the left platform",
        "lower the right platform",
    ]

    for prompt in prompts:
        print(f'   Prompt: "{prompt}"')
        cmd = prompt_to_command(prompt, state.entities)
        if cmd:
            print(f"   → {cmd.op} {cmd.id} by={cmd.by}")
            state = queue_edit(state, cmd)
        else:
            print("   → (no command generated)")
        print()

    print("3. Apply pending edits")
    state, results = apply_pending_edits(state)
    for i, result in enumerate(results):
        print(f"   Edit {i+1}: {type(result).__name__}")
    print()

    print("4. Updated world (rows 2-7):")
    print_world_section(state.world, 2, 6)
    print()

    print("5. Highlight tracking")
    print(f"   Highlight tiles: {len(state.highlight_tiles)} tiles")
    rects = tile_rects(state.highlight_tiles, TILE)
    print(f"   Highlight rects: {len(rects)} rects for rendering")
    print(f"   Highlight frames remaining: {state.highlight_frames}")
    print()

    for _ in range(10):
        state = update_highlights(state)
    print(f"   After 10 frame updates: {state.highlight_frames} frames remaining")
    print()

    print("=== Integration Demo Complete ===")


if __name__ == "__main__":
    demo()
