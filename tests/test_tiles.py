import unittest

from tilebase.geom import Rect, Vec2
from tilebase.tiles import (
    BadTileChar,
    BadTileSize,
    DuplicateChar,
    DuplicateId,
    OutOfBounds,
    RaggedRows,
    UnknownChar,
    UnknownId,
    World,
    cell_at,
    cells_overlapping,
    define,
    load_map,
    put_cell,
)


def _draw(screen: object, rect: Rect) -> None:
    return None


def _tiles():
    return (
        define(".", id="empty", draw=_draw, marks=frozenset()),
        define("#", id="solid", draw=_draw, marks=frozenset({"blocks"})),
    )


class LoadMapTest(unittest.TestCase):
    def test_loads_dense_cells(self) -> None:
        loaded = load_map((".#",), _tiles(), tile_size=16)
        self.assertIsInstance(loaded, World)
        assert isinstance(loaded, World)
        self.assertEqual((loaded.cols, loaded.rows, loaded.tile_size), (2, 1, 16))
        empty = cell_at(loaded, Vec2(1, 1))
        solid = cell_at(loaded, Vec2(16, 1))
        assert empty is not None and solid is not None
        self.assertEqual(empty.id, "empty")
        self.assertEqual(solid.marks, frozenset({"blocks"}))
        self.assertEqual(solid.rect, Rect(16, 0, 16, 16))

    def test_rejects_bad_maps(self) -> None:
        tiles = _tiles()
        self.assertEqual(load_map((), tiles, tile_size=16), RaggedRows(()))
        self.assertEqual(load_map(("..", "."), tiles, tile_size=16), RaggedRows((2, 1)))
        self.assertEqual(load_map(("?",), tiles, tile_size=16), UnknownChar("?", 0, 0))
        self.assertEqual(load_map((".",), tiles, tile_size=0), BadTileSize(0))
        self.assertIsInstance(
            load_map((".",), tiles + tiles[:1], tile_size=16),
            DuplicateChar,
        )
        dup_id = (
            define(".", id="empty", draw=_draw, marks=frozenset()),
            define("#", id="empty", draw=_draw, marks=frozenset({"blocks"})),
        )
        self.assertEqual(load_map((".",), dup_id, tile_size=16), DuplicateId("empty"))
        wide = (define("..", id="wide", draw=_draw, marks=frozenset()),)
        self.assertEqual(load_map(("..",), wide, tile_size=16), BadTileChar(".."))

    def test_point_outside_map_is_none(self) -> None:
        loaded = load_map((".",), _tiles(), tile_size=16)
        assert isinstance(loaded, World)
        self.assertIsNone(cell_at(loaded, Vec2(-1, 0)))
        self.assertIsNone(cell_at(loaded, Vec2(16, 0)))

    def test_overlap_excludes_the_far_edge(self) -> None:
        loaded = load_map((".#",), _tiles(), tile_size=16)
        assert isinstance(loaded, World)
        cells = cells_overlapping(loaded, Rect(0, 0, 16, 16))
        self.assertEqual(tuple(cell.id for cell in cells), ("empty",))

    def test_put_cell_returns_a_new_world(self) -> None:
        loaded = load_map(("..",), _tiles(), tile_size=16)
        assert isinstance(loaded, World)
        edited = put_cell(loaded, 1, 0, "solid")
        assert isinstance(edited, World)
        self.assertIsNot(edited, loaded)
        original = cell_at(loaded, Vec2(20, 1))
        changed = cell_at(edited, Vec2(20, 1))
        assert original is not None and changed is not None
        self.assertEqual(original.id, "empty")
        self.assertEqual(changed.id, "solid")
        self.assertEqual(put_cell(loaded, 4, 0, "solid"), OutOfBounds(4, 0))
        self.assertEqual(put_cell(loaded, 0, 0, "door"), UnknownId("door"))


if __name__ == "__main__":
    unittest.main()
