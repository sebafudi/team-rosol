import unittest

from tilebase.geom import Rect, Size, Vec2
from tilebase.view import fit_display, looking_at, world_to_screen


class ViewTest(unittest.TestCase):
    def test_centers_the_target_and_shifts_rects(self) -> None:
        camera = looking_at(Vec2(100, 80), Size(40, 20))
        self.assertEqual(camera.origin, Vec2(80, 70))
        self.assertEqual(camera.world_rect, Rect(80, 70, 40, 20))
        self.assertEqual(world_to_screen(camera, Rect(80, 70, 16, 16)), Rect(0, 0, 16, 16))

    def test_fit_display_fills_modern_panels(self) -> None:
        base = Size(320, 180)
        cases = (
            (Size(1280, 720), Size(320, 180), 4),
            (Size(1920, 1080), Size(320, 180), 6),
            (Size(2560, 1440), Size(320, 180), 8),
            (Size(3840, 2160), Size(320, 180), 12),
            (Size(2560, 1080), Size(426, 180), 6),
            (Size(3440, 1440), Size(430, 180), 8),
            (Size(5120, 1440), Size(640, 180), 8),
            (Size(2880, 1800), Size(320, 200), 9),
            (Size(3024, 1964), Size(336, 218), 9),
            (Size(1366, 768), Size(341, 192), 4),
            (Size(200, 100), Size(200, 100), 1),
        )
        for display, camera, scale in cases:
            with self.subTest(display=display):
                presentation = fit_display(display, base)
                covered_w = camera.w * scale
                covered_h = camera.h * scale
                self.assertEqual(presentation.camera, camera)
                self.assertEqual(presentation.scale, scale)
                self.assertEqual(presentation.x, (display.w - covered_w) // 2)
                self.assertEqual(presentation.y, (display.h - covered_h) // 2)
                self.assertLess(display.w - covered_w, scale)
                self.assertLess(display.h - covered_h, scale)

    def test_fitted_camera_still_centers_the_target(self) -> None:
        presentation = fit_display(Size(2560, 1080), Size(320, 180))
        camera = looking_at(Vec2(100, 80), presentation.camera)
        center = world_to_screen(camera, Rect(100, 80, 0, 0))
        self.assertEqual((center.x, center.y), (presentation.camera.w / 2, presentation.camera.h / 2))


if __name__ == "__main__":
    unittest.main()
