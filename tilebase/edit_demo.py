"""Demo for the named map-object edit API.

Run with: python -m tilebase.edit_demo

Shows a simple level with two named platforms, applies a move command,
and prints the before/after states plus collision verification.
"""

from tilebase.art import tile_drawer
from tilebase.geom import Rect, Vec2
from tilebase.move import Body, Moved, move_body
from tilebase.tiles import Cell, World, define, load_map

from tilebase.edit import (
    Command,
    EditSuccess,
    Entity,
    apply_edit,
    define_entities,
)


TILE = 32

DEMO_MAP = (
    "####################",
    "#..................#",
    "#..................#",
    "#..................#",
    "#...####...........#",
    "#..................#",
    "#............####..#",
    "#..................#",
    "#..................#",
    "####################",
)


def _draw_empty(screen: object, rect: Rect) -> None:
    return None


def blocks(cell: Cell, body: Body, delta: Vec2) -> bool:
    return "blocks" in cell.marks


def print_world_section(world: World, row_start: int, row_count: int) -> None:
    """Print a section of the world grid for visualization."""
    from tilebase.tiles import _cell

    for r in range(row_start, min(row_start + row_count, world.rows)):
        line = ""
        for c in range(world.cols):
            cell = _cell(world, c, r)
            line += "#" if "blocks" in cell.marks else "."
        print(f"  {line}")


def demo() -> None:
    print("=== Named Map-Object Edit API Demo ===\n")

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

    print("1. Define named entities")
    print("   - plat_left: 4-tile platform at row 4")
    print("   - plat_right: 4-tile platform at row 6\n")

    world, entities = define_entities(
        world,
        (
            Entity(id="plat_left", type="platform", tiles=((4, 4), (5, 4), (6, 4), (7, 4))),
            Entity(id="plat_right", type="platform", tiles=((13, 6), (14, 6), (15, 6), (16, 6))),
        ),
        bounds=Rect(0, 0, 20 * TILE, 10 * TILE),
        spawn_rect=Rect(2 * TILE, 7 * TILE, 12, 14),
    )

    print("Initial world (rows 3-7):")
    print_world_section(world, 3, 5)
    print()

    print("2. Apply command: move plat_left up by 2 tiles\n")
    cmd = Command(op="move", id="plat_left", by=(0, -2))
    result = apply_edit(world, entities, cmd)

    if isinstance(result, EditSuccess):
        print("✓ Edit succeeded")
        print(f"  Changed tiles: {len(result.changed_tiles)} tiles modified\n")

        print("Updated world (rows 1-7):")
        print_world_section(result.world, 1, 7)
        print()

        print("3. Verify collision detection")
        body_start = Body(Rect(4 * TILE, 1 * TILE, 12, 14))
        moved = move_body(result.world, body_start, Vec2(0, TILE + 10), blocks)
        if moved.blocked_y:
            print("✓ Body moving down collides with raised platform")
        else:
            print("✗ Expected collision not detected")
        print()

        print("4. Test safety: attempt to move platform onto spawn")
        bad_cmd = Command(op="move", id="plat_right", by=(-11, 1))
        bad_result = apply_edit(result.world, result.entities, bad_cmd)
        print(f"   Result: {type(bad_result).__name__}")
        if hasattr(bad_result, "tiles"):
            print(f"   Rejected tiles: {bad_result.tiles}")
        print()

        print("=== Demo Complete ===")
    else:
        print(f"✗ Edit failed: {type(result).__name__}")
        if hasattr(result, "__dict__"):
            for k, v in result.__dict__.items():
                print(f"  {k}: {v}")


if __name__ == "__main__":
    demo()
