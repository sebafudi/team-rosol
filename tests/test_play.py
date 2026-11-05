import math
import unittest

from tilebase.geom import Size, Vec2
from tilebase.play import (
    SANDBOX,
    TICK,
    MAX_TICKS_PER_FRAME,
    axis,
    clamp_cam,
    follow,
    sandbox,
    spawn_point,
    ticks_for,
)


class PlayTest(unittest.TestCase):
    def test_sandbox_loads_and_has_a_spawn(self) -> None:
        world = sandbox()
        self.assertEqual(world.cols, len(SANDBOX[0]))
        start = spawn_point(SANDBOX)
        self.assertGreater(start.x, 0)

    def test_accumulator_runs_whole_ticks_and_keeps_the_rest(self) -> None:
        n, acc = ticks_for(0.0, TICK * 2.5)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(acc, TICK * 0.5)

    def test_accumulator_caps_a_long_hitch(self) -> None:
        n, _ = ticks_for(0.0, 5.0)
        self.assertEqual(n, MAX_TICKS_PER_FRAME)

    def test_axis_cancels_opposites(self) -> None:
        self.assertEqual(axis(True, True), 0)
        self.assertEqual(axis(True, False), -1)

    def test_follow_is_frame_rate_independent(self) -> None:
        one = follow(Vec2(0, 0), Vec2(100, 0), 0.1)
        many = Vec2(0, 0)
        for _ in range(10):
            many = follow(many, Vec2(100, 0), 0.01)
        self.assertTrue(math.isclose(one.x, many.x, rel_tol=1e-9))

    def test_camera_stays_inside_the_world(self) -> None:
        world = sandbox()
        cam = clamp_cam(Vec2(-500, -500), world, Size(640, 360))
        self.assertEqual(cam, Vec2(320, 180))


if __name__ == "__main__":
    unittest.main()
