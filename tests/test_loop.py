import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from tilebase.demo import blocks, draw_body, plan_move, world
from tilebase.geom import Rect, Size, Vec2
from tilebase.loop import BACKDROP, open_fullscreen, present, read_keys, run, wants_quit
from tilebase.move import Body, Frame, Keys
from tilebase.tiles import cell_at


class LoopTest(unittest.TestCase):
    def test_read_keys_uses_arrows_and_space(self) -> None:
        held = {pygame.K_a: True, pygame.K_SPACE: True}

        class Pressed:
            def __getitem__(self, index: int) -> bool:
                return bool(held.get(index, False))

        keys = read_keys(Pressed())
        self.assertEqual(
            keys,
            Keys(left=True, right=False, up=False, down=False, action=True),
        )

    def test_plan_move_ignores_gravity(self) -> None:
        frame = Frame(
            keys=Keys(left=False, right=True, up=False, down=False, action=False),
            dt=0.5,
            body=Body(Rect(0, 0, 10, 10)),
            world=world(),
        )
        self.assertEqual(plan_move(frame), pygame_vec())

    def test_demo_tiles_are_32_pixels(self) -> None:
        level = world()
        corner = cell_at(level, Vec2(0, 0))
        assert corner is not None
        self.assertEqual(corner.rect, Rect(0, 0, 32, 32))

    def test_escape_and_close_request_quit(self) -> None:
        self.assertTrue(wants_quit(pygame.event.Event(pygame.QUIT)))
        self.assertTrue(wants_quit(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)))
        self.assertFalse(wants_quit(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a)))

    def test_fullscreen_camera_covers_the_display(self) -> None:
        screen, canvas, fitted = open_fullscreen(Size(320, 180))
        canvas.fill((255, 0, 0))
        present(screen, canvas, fitted)
        covered_w = fitted.camera.w * fitted.scale
        covered_h = fitted.camera.h * fitted.scale
        self.assertTrue(screen.get_flags() & pygame.FULLSCREEN)
        self.assertEqual(canvas.get_size(), (fitted.camera.w, fitted.camera.h))
        self.assertEqual(screen.get_at((fitted.x, fitted.y))[:3], (255, 0, 0))
        self.assertEqual(
            screen.get_at((fitted.x + covered_w - 1, fitted.y + covered_h - 1))[:3],
            (255, 0, 0),
        )
        self.assertLess(screen.get_width() - covered_w, fitted.scale)
        self.assertLess(screen.get_height() - covered_h, fitted.scale)
        if fitted.x + covered_w < screen.get_width():
            self.assertEqual(screen.get_at((screen.get_width() - 1, fitted.y))[:3], BACKDROP)
        if fitted.y + covered_h < screen.get_height():
            self.assertEqual(screen.get_at((fitted.x, screen.get_height() - 1))[:3], BACKDROP)
        pygame.quit()

    def test_run_draws_two_dummy_frames(self) -> None:
        body = run(
            world=world(),
            body=Body(Rect(32, 32, 12, 14)),
            screen_size=Size(320, 180),
            plan_move=plan_move,
            blocks=blocks,
            draw_body=draw_body,
            max_frames=2,
        )
        self.assertEqual(body.rect, Rect(32, 32, 12, 14))


def pygame_vec():
    from tilebase.geom import Vec2

    return Vec2(60.0, 0.0)


if __name__ == "__main__":
    unittest.main()
