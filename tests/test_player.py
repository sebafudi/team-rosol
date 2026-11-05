import unittest
from dataclasses import replace

from tilebase.geom import Rect, Vec2
from tilebase.move import Body
from tilebase.player import Input, Player, Tuning, spawn, step
from tilebase.tiles import Cell, World, define, load_map

DT = 1 / 120
TILE = 32
IDLE = Input(x=0, y=0, jump=False, jump_pressed=False, dash_pressed=False)


def _draw(screen: object, rect: Rect) -> None:
    return None


def _world(*rows: str) -> World:
    loaded = load_map(
        rows,
        (
            define(".", id="empty", draw=_draw, marks=frozenset()),
            define("#", id="solid", draw=_draw, marks=frozenset({"blocks"})),
        ),
        tile_size=TILE,
    )
    assert isinstance(loaded, World)
    return loaded


def _blocks(cell: Cell, body: Body, delta: Vec2) -> bool:
    return "blocks" in cell.marks


def _inp(
    x: int = 0,
    y: int = 0,
    jump: bool = False,
    jump_pressed: bool = False,
    dash_pressed: bool = False,
) -> Input:
    return Input(x, y, jump, jump_pressed, dash_pressed)


def _run(p: Player, world: World, inp: Input, ticks: int) -> Player:
    for _ in range(ticks):
        p = step(p, inp, world, _blocks, DT)
    return p


def _bottom(p: Player) -> float:
    return p.body.rect.y + p.body.rect.h


FLAT = (
    "........................................",
    "........................................",
    "........................................",
    "........................................",
    "........................................",
    "........................................",
    "########################################",
)
FLOOR_Y = 6 * TILE


def _on_floor(world: World, col: float = 5) -> Player:
    t = Tuning()
    p = spawn(col * TILE, FLOOR_Y - t.height)
    return _run(p, world, IDLE, 2)


def _jump_height(world: World, hold_ticks: int) -> float:
    p = _on_floor(world)
    start = _bottom(p)
    top = start
    p = step(p, _inp(jump=True, jump_pressed=True), world, _blocks, DT)
    for i in range(240):
        held = i + 1 < hold_ticks
        p = step(p, _inp(jump=held), world, _blocks, DT)
        top = min(top, _bottom(p))
        if p.on_ground:
            break
    return start - top


class RunTest(unittest.TestCase):
    def test_spawned_player_settles_on_floor(self) -> None:
        p = _on_floor(_world(*FLAT))
        self.assertTrue(p.on_ground)
        self.assertAlmostEqual(_bottom(p), FLOOR_Y)

    def test_runs_to_max_speed_quickly(self) -> None:
        world = _world(*FLAT)
        p = _run(_on_floor(world), world, _inp(x=1), 12)
        self.assertAlmostEqual(p.vel.x, 360.0)
        self.assertEqual(p.facing, 1)

    def test_stops_quickly(self) -> None:
        world = _world(*FLAT)
        p = _run(_on_floor(world), world, _inp(x=1), 20)
        p = _run(p, world, IDLE, 28)
        self.assertEqual(p.vel.x, 0.0)

    def test_turnaround_is_fast(self) -> None:
        world = _world(*FLAT)
        p = _run(_on_floor(world), world, _inp(x=1), 20)
        p = _run(p, world, _inp(x=-1), 24)
        self.assertAlmostEqual(p.vel.x, -360.0)
        self.assertEqual(p.facing, -1)


class JumpTest(unittest.TestCase):
    def test_full_jump_is_two_to_three_and_a_half_tiles(self) -> None:
        height = _jump_height(_world(*FLAT), hold_ticks=999)
        print(f"\nfull jump height: {height:.1f}px ({height / TILE:.2f} tiles)")
        self.assertGreater(height, 64.0)
        self.assertLess(height, 112.0)

    def test_short_hop_is_much_lower_than_full_jump(self) -> None:
        world = _world(*FLAT)
        full = _jump_height(world, hold_ticks=999)
        hop = _jump_height(world, hold_ticks=1)
        print(f"\nshort hop height: {hop:.1f}px (full {full:.1f}px)")
        self.assertLess(hop, full * 0.4)
        self.assertGreater(hop, 0.0)

    def test_jump_emits_events(self) -> None:
        world = _world(*FLAT)
        p = step(_on_floor(world), _inp(jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertIn("jump", p.events)
        self.assertIn("leave_ground", p.events)
        p = _run(p, world, IDLE, 120)
        self.assertTrue(p.on_ground)

    def test_landing_reports_impact(self) -> None:
        world = _world(*FLAT)
        p = spawn(5 * TILE, 0)
        for _ in range(240):
            p = step(p, IDLE, world, _blocks, DT)
            if "land" in p.events:
                break
        self.assertIn("land", p.events)
        self.assertGreater(p.impact, 300.0)

    def test_fast_fall_raises_the_cap_gradually(self) -> None:
        world = _world(*(["." * 4] * 60 + ["#" * 4]))
        p = _run(spawn(TILE, 0), world, IDLE, 60)
        self.assertAlmostEqual(p.vel.y, 640.0)
        p = step(p, _inp(y=1), world, _blocks, DT)
        self.assertLess(p.vel.y, 960.0)
        p = _run(p, world, _inp(y=1), 20)
        self.assertAlmostEqual(p.vel.y, 960.0)


LEDGE = (
    "........................................",
    "........................................",
    "........................................",
    "........................................",
    "######..................................",
    "........................................",
    "........................................",
    "........................................",
    "........................................",
    "########################################",
)


def _walked_off(world: World, air_ticks: int) -> Player:
    """Walk right off the ledge top, then stay airborne for `air_ticks`."""
    t = Tuning()
    p = spawn(5 * TILE - t.width - 2, 4 * TILE - t.height)
    p = _run(p, world, IDLE, 2)
    p = replace_vel(p, 360.0)
    while p.on_ground:
        p = step(p, _inp(x=1), world, _blocks, DT)
    return _run(p, world, _inp(x=1), air_ticks - 1)


def replace_vel(p: Player, vx: float) -> Player:
    return replace(p, vel=Vec2(vx, p.vel.y))


class ForgivenessTest(unittest.TestCase):
    def test_coyote_jump_after_a_short_fall(self) -> None:
        world = _world(*LEDGE)
        p = _walked_off(world, air_ticks=6)
        self.assertFalse(p.on_ground)
        p = step(p, _inp(x=1, jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertIn("jump", p.events)
        self.assertLess(p.vel.y, 0.0)

    def test_no_coyote_jump_after_a_long_fall(self) -> None:
        world = _world(*LEDGE)
        p = _walked_off(world, air_ticks=18)
        p = step(p, _inp(x=1, jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertNotIn("jump", p.events)
        self.assertGreater(p.vel.y, 0.0)

    def test_buffered_jump_fires_on_landing(self) -> None:
        world = _world(*FLAT)
        p = spawn(5 * TILE, FLOOR_Y - 22 - 30)
        while _bottom(p) < FLOOR_Y - 10:
            p = step(p, IDLE, world, _blocks, DT)
        p = step(p, _inp(jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertNotIn("jump", p.events)
        jumped = False
        for _ in range(12):
            p = step(p, _inp(jump=True), world, _blocks, DT)
            jumped = jumped or "jump" in p.events
        self.assertTrue(jumped)
        self.assertLess(p.vel.y, 0.0)

    def test_buffered_jump_expires(self) -> None:
        world = _world(*(["." * 4] * 10 + ["#" * 4]))
        p = spawn(TILE, 0)
        p = step(p, _inp(jump=True, jump_pressed=True), world, _blocks, DT)
        jumped = False
        for _ in range(240):
            p = step(p, _inp(jump=True), world, _blocks, DT)
            jumped = jumped or "jump" in p.events
        self.assertFalse(jumped)
        self.assertTrue(p.on_ground)


WELL = (
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "..........#",
    "###########",
)
WALL_X = 10 * TILE


def _falling_by_wall(world: World, ticks: int = 30) -> Player:
    t = Tuning()
    p = spawn(WALL_X - t.width, TILE)
    return _run(p, world, _inp(x=1), ticks)


class WallTest(unittest.TestCase):
    def test_wall_slide_caps_fall_speed(self) -> None:
        world = _world(*WELL)
        p = _falling_by_wall(world, ticks=60)
        self.assertEqual(p.wall_dir, 1)
        self.assertTrue(p.wall_sliding)
        self.assertAlmostEqual(p.vel.y, 80.0)

    def test_no_slide_without_holding_toward_wall(self) -> None:
        world = _world(*WELL)
        t = Tuning()
        p = _run(spawn(WALL_X - t.width, TILE), world, IDLE, 40)
        self.assertEqual(p.wall_dir, 1)
        self.assertFalse(p.wall_sliding)
        self.assertGreater(p.vel.y, 400.0)

    def test_wall_jump_pushes_away_and_locks_input(self) -> None:
        world = _world(*WELL)
        p = _falling_by_wall(world)
        p = step(p, _inp(x=1, jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertIn("wall_jump", p.events)
        self.assertEqual(p.facing, -1)
        self.assertLess(p.vel.y, -400.0)
        self.assertLess(p.vel.x, -400.0)
        p = _run(p, world, _inp(x=1, jump=True), 12)
        self.assertLess(p.vel.x, -300.0, "toward-wall input is ignored during lock")
        self.assertLess(p.body.rect.x + p.body.rect.w, WALL_X - 40)

    def test_wall_jump_from_a_few_pixels_away(self) -> None:
        world = _world(*WELL)
        t = Tuning()
        p = _run(spawn(WALL_X - t.width - 10, TILE), world, IDLE, 20)
        self.assertEqual(p.wall_dir, 0)
        p = step(p, _inp(jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertIn("wall_jump", p.events)
        self.assertLess(p.vel.x, 0.0)

    def test_no_wall_jump_far_from_wall(self) -> None:
        world = _world(*WELL)
        t = Tuning()
        p = _run(spawn(WALL_X - t.width - 20, TILE), world, IDLE, 20)
        p = step(p, _inp(jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertNotIn("wall_jump", p.events)


if __name__ == "__main__":
    unittest.main()
