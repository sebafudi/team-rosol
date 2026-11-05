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


OPEN = tuple(["." * 40] * 20 + ["#" * 40])


def _dash_distance(world: World, p: Player, inp: Input) -> tuple[Player, float]:
    """Dash with `inp`, then hold nothing until the dash ends; return x travelled."""
    x0 = p.body.rect.x
    p = step(p, inp, world, _blocks, DT)
    while p.dashing:
        p = step(p, IDLE, world, _blocks, DT)
    return p, p.body.rect.x - x0


class DashTest(unittest.TestCase):
    def test_ground_dash_distance_and_exit_speed(self) -> None:
        world = _world(*FLAT)
        p, dist = _dash_distance(world, _on_floor(world, 2), _inp(dash_pressed=True))
        print(f"\ndash distance (dash phase only): {dist:.1f}px ({dist / TILE:.2f} tiles)")
        self.assertIn("dash_end", p.events)
        self.assertAlmostEqual(dist, 960 * 0.15, delta=10)
        self.assertAlmostEqual(p.vel.x, 640.0, delta=20)

    def test_dash_ignores_gravity_and_input(self) -> None:
        world = _world(*OPEN)
        p = _run(spawn(5 * TILE, 5 * TILE), world, IDLE, 1)
        y0 = p.body.rect.y
        p = step(p, _inp(x=1, dash_pressed=True), world, _blocks, DT)
        self.assertIn("dash", p.events)
        for _ in range(10):
            p = step(p, _inp(x=-1, y=1), world, _blocks, DT)
            self.assertTrue(p.dashing)
            self.assertAlmostEqual(p.vel.x, 960.0)
            self.assertAlmostEqual(p.vel.y, 0.0)
        self.assertLess(abs(p.body.rect.y - y0), 1.0)

    def test_diagonal_up_dash_exit_is_damped(self) -> None:
        world = _world(*OPEN)
        p = _run(spawn(5 * TILE, 15 * TILE), world, IDLE, 1)
        p, _ = _dash_distance(world, p, _inp(x=1, y=-1, dash_pressed=True))
        diag = 640 * 0.5**0.5
        self.assertAlmostEqual(p.vel.x, diag, delta=20)
        self.assertLess(p.vel.y, 0.0)
        self.assertGreater(p.vel.y, -0.75 * diag - 40)

    def test_dash_refills_only_on_landing(self) -> None:
        world = _world(*OPEN)
        p = _run(spawn(5 * TILE, 10 * TILE), world, IDLE, 1)
        self.assertEqual(p.dashes_left, 1)
        p, _ = _dash_distance(world, p, _inp(dash_pressed=True))
        self.assertEqual(p.dashes_left, 0)
        p = step(p, _inp(dash_pressed=True), world, _blocks, DT)
        self.assertNotIn("dash", p.events)
        while not p.on_ground:
            p = step(p, IDLE, world, _blocks, DT)
        self.assertIn("land", p.events)
        self.assertEqual(p.dashes_left, 1)

    def test_dash_press_is_buffered(self) -> None:
        world = _world(*OPEN)
        p = _run(spawn(5 * TILE, 10 * TILE), world, IDLE, 1)
        p, _ = _dash_distance(world, p, _inp(dash_pressed=True))
        while _bottom(p) < 20 * TILE - 30:
            p = step(p, IDLE, world, _blocks, DT)
        p = step(p, _inp(dash_pressed=True), world, _blocks, DT)
        self.assertNotIn("dash", p.events)
        dashed = False
        for _ in range(8):
            p = step(p, IDLE, world, _blocks, DT)
            dashed = dashed or "dash" in p.events
        self.assertTrue(dashed)

    def test_dash_jump_keeps_horizontal_speed(self) -> None:
        world = _world(*FLAT)
        p = _on_floor(world, 2)
        p = _run(p, world, _inp(x=1, dash_pressed=True), 1)
        p = _run(p, world, _inp(x=1), 5)
        p = step(p, _inp(x=1, jump=True, jump_pressed=True), world, _blocks, DT)
        self.assertIn("jump", p.events)
        self.assertFalse(p.dashing)
        self.assertAlmostEqual(p.vel.x, 960.0)
        self.assertEqual(p.dashes_left, 1)


CEILING_BLOCK = (
    "................",
    "................",
    "................",
    ".....#..........",
    "................",
    "................",
    "################",
)
BLOCK_RIGHT = 6 * TILE


def _jump_under_block(overlap: float) -> Player:
    """Jump straight up with the head overlapping the block's right edge."""
    world = _world(*CEILING_BLOCK)
    p = _run(spawn(BLOCK_RIGHT - overlap, FLOOR_Y - 22), world, IDLE, 2)
    p = step(p, _inp(jump=True, jump_pressed=True), world, _blocks, DT)
    for _ in range(30):
        p = step(p, _inp(jump=True), world, _blocks, DT)
        if "bonk" in p.events or p.body.rect.y < 3 * TILE:
            break
    return p


STEP_UP = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "..........######",
    "################",
)
STEP_X = 10 * TILE
STEP_TOP = 5 * TILE


def _airborne_into_step(lip: float) -> Player:
    """Moving right while the body's bottom is `lip` px below the step's top."""
    world = _world(*STEP_UP)
    t = Tuning()
    p = spawn(STEP_X - t.width - 1, STEP_TOP + lip - t.height)
    p = replace(p, vel=Vec2(360.0, 0.0))
    return _run(p, world, _inp(x=1), 12)


EDGE = (
    "................",
    "................",
    "................",
    "................",
    "#####...........",
    "................",
    "................",
    "################",
)
EDGE_X = 5 * TILE


def _perched(supported: float) -> Player:
    world = _world(*EDGE)
    t = Tuning()
    return spawn(EDGE_X - supported, 4 * TILE - t.height)


class CornerTest(unittest.TestCase):
    def test_head_slips_past_a_ceiling_corner(self) -> None:
        p = _jump_under_block(overlap=8)
        self.assertNotIn("bonk", p.events)
        self.assertGreaterEqual(p.body.rect.x, BLOCK_RIGHT)
        self.assertLess(p.body.rect.y, 3 * TILE)

    def test_bonks_when_overlap_is_too_deep(self) -> None:
        p = _jump_under_block(overlap=16)
        self.assertIn("bonk", p.events)
        self.assertEqual(p.vel.y, 0.0)

    def test_round_body_pops_over_a_small_lip(self) -> None:
        p = _airborne_into_step(lip=7)
        self.assertGreater(p.body.rect.x, STEP_X)
        self.assertLessEqual(_bottom(p), STEP_TOP + 1e-6)
        self.assertGreater(p.vel.x, 300.0)

    def test_tall_lip_still_blocks(self) -> None:
        p = _airborne_into_step(lip=14)
        self.assertLessEqual(p.body.rect.x + p.body.rect.w, STEP_X + 1e-6)
        self.assertEqual(p.vel.x, 0.0)


class RoundBodyTest(unittest.TestCase):
    def test_idle_blob_rolls_off_a_thin_edge(self) -> None:
        world = _world(*EDGE)
        p = _run(_perched(supported=5), world, IDLE, 1)
        self.assertIn("edge_nudge", p.events)
        self.assertGreater(p.vel.x, 0.0)
        p = _run(p, world, IDLE, 30)
        self.assertFalse(p.on_ground)
        self.assertGreater(p.body.rect.x, EDGE_X)

    def test_holding_a_direction_disables_the_nudge(self) -> None:
        world = _world(*EDGE)
        p = _run(_perched(supported=5), world, _inp(x=-1), 1)
        self.assertNotIn("edge_nudge", p.events)
        self.assertLess(p.vel.x, 0.0)

    def test_well_supported_blob_stays_put(self) -> None:
        world = _world(*EDGE)
        start = _perched(supported=10)
        p = _run(start, world, IDLE, 30)
        self.assertTrue(p.on_ground)
        self.assertAlmostEqual(p.body.rect.x, start.body.rect.x)

    def test_hard_landing_keeps_horizontal_speed(self) -> None:
        world = _world(*OPEN)
        p = replace(spawn(2 * TILE, 0), vel=Vec2(600.0, 0.0))
        while not p.on_ground:
            p = step(p, _inp(x=1, y=1), world, _blocks, DT)
        self.assertGreater(p.impact, 700.0)
        landed_vx = p.vel.x
        p = step(p, _inp(x=1), world, _blocks, DT)
        self.assertAlmostEqual(p.vel.x, landed_vx)


if __name__ == "__main__":
    unittest.main()
