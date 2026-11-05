import unittest

from tilebase.geom import Rect, Size, Vec2
from tilebase.view import looking_at, world_to_screen


class ViewTest(unittest.TestCase):
    def test_centers_the_target_and_shifts_rects(self) -> None:
        camera = looking_at(Vec2(100, 80), Size(40, 20))
        self.assertEqual(camera.origin, Vec2(80, 70))
        self.assertEqual(camera.world_rect, Rect(80, 70, 40, 20))
        self.assertEqual(world_to_screen(camera, Rect(80, 70, 16, 16)), Rect(0, 0, 16, 16))


if __name__ == "__main__":
    unittest.main()
