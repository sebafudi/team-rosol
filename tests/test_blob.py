import os
import unittest
from dataclasses import dataclass

from tilebase.blob import Look, blink_amount, draw_blob, rest, update_look
from tilebase.geom import Vec2

DT = 1.0 / 60.0


@dataclass(frozen=True)
class FakePlayer:
    vel: Vec2 = Vec2(0.0, 0.0)
    on_ground: bool = True
    facing: int = 1
    wall_dir: int = 0
    wall_sliding: bool = False
    dashing: bool = False
    dashes_left: int = 1
    events: frozenset[str] = frozenset()
    impact: float = 0.0


def step(look: Look, player: FakePlayer, frames: int = 1) -> Look:
    for _ in range(frames):
        look = update_look(look, player, 0, 0, DT)
    return look


def landed(impact: float) -> Look:
    return step(rest(), FakePlayer(events=frozenset({"land"}), impact=impact))


class LookTest(unittest.TestCase):
    def test_land_squashes_wide_and_scales_with_impact(self) -> None:
        soft = landed(200.0)
        hard = landed(900.0)
        self.assertGreater(hard.sx, hard.sy)
        self.assertGreater(soft.sx, soft.sy)
        self.assertGreater(hard.sx - hard.sy, soft.sx - soft.sy)

    def test_springs_settle_within_half_a_second_after_landing(self) -> None:
        look = step(landed(960.0), FakePlayer(), frames=30)
        self.assertAlmostEqual(look.sx, 1.0, delta=0.02)
        self.assertAlmostEqual(look.sy, 1.0, delta=0.02)

    def test_jump_stretches_tall(self) -> None:
        air = FakePlayer(vel=Vec2(0.0, -420.0), on_ground=False)
        look = step(rest(), FakePlayer(vel=air.vel, on_ground=False, events=frozenset({"jump"})))
        look = step(look, air, frames=2)
        self.assertGreater(look.sy, look.sx)

    def test_blinks_within_six_seconds(self) -> None:
        look = rest()
        seen = False
        for _ in range(int(6.0 / DT)):
            look = step(look, FakePlayer())
            seen = seen or blink_amount(look) > 0.5
        self.assertTrue(seen)
        self.assertGreaterEqual(look.blinks, 1)

    def test_update_is_deterministic(self) -> None:
        def run() -> Look:
            look = landed(700.0)
            moving = FakePlayer(vel=Vec2(300.0, 0.0))
            for _ in range(400):
                look = update_look(look, moving, 1, 0, DT)
            return look

        self.assertEqual(run(), run())

    def test_dash_rotates_along_velocity(self) -> None:
        dash = FakePlayer(vel=Vec2(0.0, -960.0), on_ground=False, dashing=True, events=frozenset({"dash"}))
        look = step(rest(), dash)
        self.assertAlmostEqual(look.angle, -1.5708, places=3)
        self.assertGreater(look.sx, look.sy)


class DrawTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    def test_draws_on_a_surface(self) -> None:
        import pygame

        screen = pygame.Surface((64, 64))
        dash = FakePlayer(vel=Vec2(700.0, 300.0), on_ground=False, dashing=True, events=frozenset({"dash"}))
        for look in (rest(), landed(900.0), step(rest(), dash)):
            for dashes in (0, 1):
                draw_blob(screen, Vec2(32.0, 32.0), look, dashes_left=dashes)
        self.assertNotEqual(screen.get_at((32, 32))[:3], (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
