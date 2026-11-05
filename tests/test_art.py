import os
import unittest
from dataclasses import dataclass

from tilebase.art import TILE_NAMES, backdrop_offset, draw_backdrop, draw_player, pose_for, tile_drawer
from tilebase.blob import rest
from tilebase.geom import Rect, Size, Vec2


@dataclass(frozen=True)
class FakePlayer:
    on_ground: bool = True
    facing: int = 1
    wall_dir: int = 0
    wall_sliding: bool = False


class PoseTest(unittest.TestCase):
    def test_ground_uses_idle_mirrored_by_facing(self) -> None:
        self.assertEqual(pose_for(FakePlayer()), ("idle", False))
        self.assertEqual(pose_for(FakePlayer(facing=-1)), ("idle", True))

    def test_air_uses_jump(self) -> None:
        self.assertEqual(pose_for(FakePlayer(on_ground=False)), ("jump", False))

    def test_wall_slide_hugs_the_wall(self) -> None:
        right = FakePlayer(on_ground=False, wall_sliding=True, wall_dir=1, facing=-1)
        left = FakePlayer(on_ground=False, wall_sliding=True, wall_dir=-1, facing=1)
        self.assertEqual(pose_for(right), ("climb", False))
        self.assertEqual(pose_for(left), ("climb", True))


class BackdropTest(unittest.TestCase):
    VIEW = Size(640, 360)
    ART = Size(800, 450)
    WORLD = Size(2000, 480)

    def test_left_edge_shows_art_left_edge(self) -> None:
        at = backdrop_offset(Vec2(320, 180), self.WORLD, self.VIEW, self.ART)
        self.assertEqual(at, Vec2(0.0, 0.0))

    def test_far_edge_shows_art_far_edge(self) -> None:
        at = backdrop_offset(Vec2(1680, 300), self.WORLD, self.VIEW, self.ART)
        self.assertEqual(at, Vec2(-160.0, -90.0))

    def test_world_smaller_than_view_centres_art(self) -> None:
        at = backdrop_offset(Vec2(100, 100), Size(200, 200), self.VIEW, self.ART)
        self.assertEqual(at, Vec2(-80.0, -45.0))


class DrawTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

    def test_every_tile_draws_its_art(self) -> None:
        import pygame

        screen = pygame.Surface((32, 32))
        for name in TILE_NAMES:
            screen.fill((255, 0, 255))
            tile_drawer(name)(screen, Rect(0, 0, 32, 32))
            painted = sum(
                tuple(screen.get_at((x, y)))[:3] != (255, 0, 255)
                for x in range(32)
                for y in range(32)
            )
            self.assertGreater(painted, 32, name)

    def test_backdrop_covers_the_view(self) -> None:
        import pygame

        screen = pygame.Surface((64, 36))
        screen.fill((255, 0, 255))
        draw_backdrop(screen, Vec2(32, 18), Size(64, 36), Size(64, 36))
        for corner in ((0, 0), (63, 0), (0, 35), (63, 35)):
            self.assertNotEqual(tuple(screen.get_at(corner))[:3], (255, 0, 255))

    def test_player_paints_a_dark_ball_at_center(self) -> None:
        import pygame

        screen = pygame.Surface((64, 64))
        screen.fill((255, 255, 255))
        draw_player(screen, Vec2(32, 32), FakePlayer(), rest(), dashes_left=1)
        r, g, b = tuple(screen.get_at((32, 36)))[:3]
        self.assertLess(r + g + b, 120)
        self.assertEqual(tuple(screen.get_at((1, 1)))[:3], (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
