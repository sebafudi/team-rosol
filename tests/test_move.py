import unittest

from tilebase.geom import Rect, Vec2
from tilebase.move import Body, move_body
from tilebase.tiles import Cell, World, define, load_map, put_cell


def _draw(screen: object, rect: Rect) -> None:
    return None


def _world() -> World:
    loaded = load_map(
        (
            ".......",
            ".......",
            "..#.#..",
            "#######",
        ),
        (
            define(".", id="empty", draw=_draw, marks=frozenset()),
            define("#", id="solid", draw=_draw, marks=frozenset({"blocks"})),
            define("=", id="one_way", draw=_draw, marks=frozenset({"one_way"})),
        ),
        tile_size=16,
    )
    assert isinstance(loaded, World)
    return loaded


def _blocks(cell: Cell, body: Body, delta: Vec2) -> bool:
    if "blocks" in cell.marks:
        return True
    if "one_way" in cell.marks and delta.y > 0:
        return body.rect.y + body.rect.h <= cell.rect.y + 1e-6
    return False


class MoveBodyTest(unittest.TestCase):
    def test_slides_until_a_solid_edge(self) -> None:
        world = _world()
        body = Body(Rect(16, 32, 12, 16))
        moved = move_body(world, body, Vec2(100, 0), _blocks)
        self.assertTrue(moved.blocked_x)
        self.assertFalse(moved.blocked_y)
        self.assertAlmostEqual(moved.body.rect.x, 20.0)

    def test_lands_on_a_solid_floor(self) -> None:
        world = _world()
        moved = move_body(world, Body(Rect(16, 20, 12, 16)), Vec2(0, 40), _blocks)
        self.assertTrue(moved.blocked_y)
        self.assertAlmostEqual(moved.body.rect.y, 32.0)

    def test_does_not_tunnel_past_a_one_tile_wall(self) -> None:
        world = _world()
        body = Body(Rect(0, 32, 10, 16))
        moved = move_body(world, body, Vec2(400, 0), _blocks)
        self.assertTrue(moved.blocked_x)
        self.assertLess(moved.body.rect.x + moved.body.rect.w, 32.0 + 1e-6)
        self.assertAlmostEqual(moved.body.rect.x, 22.0)

    def test_one_way_blocks_only_a_downward_landing(self) -> None:
        world = _world()
        edited = put_cell(world, 3, 2, "one_way")
        assert isinstance(edited, World)
        falling = move_body(edited, Body(Rect(52, 0, 10, 16)), Vec2(0, 80), _blocks)
        self.assertTrue(falling.blocked_y)
        self.assertAlmostEqual(falling.body.rect.y, 16.0)
        rising = move_body(edited, Body(Rect(52, 40, 10, 16)), Vec2(0, -40), _blocks)
        self.assertFalse(rising.blocked_y)
        self.assertAlmostEqual(rising.body.rect.y, 0.0)

    def test_edit_changes_the_next_move(self) -> None:
        world = _world()
        body = Body(Rect(0, 32, 12, 16))
        opened = put_cell(put_cell(world, 2, 2, "empty"), 4, 2, "empty")
        assert isinstance(opened, World)
        moved = move_body(opened, body, Vec2(40, 0), _blocks)
        self.assertFalse(moved.blocked_x)
        self.assertAlmostEqual(moved.body.rect.x, 40.0)


if __name__ == "__main__":
    unittest.main()
