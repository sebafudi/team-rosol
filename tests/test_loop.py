import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from tilebase.demo import blocks, draw_body, plan_move, world
from tilebase.geom import Rect, Size, Vec2
from tilebase.loop import read_keys, run
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
