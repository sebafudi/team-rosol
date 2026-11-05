from __future__ import annotations

from typing import Protocol

from tilebase.geom import Rect, Size
from tilebase.move import Blocks, Body, Frame, Keys, PlanMove, move_body
from tilebase.tiles import DrawFn, World, cells_overlapping
from tilebase.view import looking_at, world_to_screen


class Pressed(Protocol):
    def __getitem__(self, index: int) -> bool: ...


def read_keys(pressed: Pressed) -> Keys:
    import pygame

    def down(code: int) -> bool:
        return bool(pressed[code])

    return Keys(
        left=down(pygame.K_LEFT) or down(pygame.K_a),
        right=down(pygame.K_RIGHT) or down(pygame.K_d),
        up=down(pygame.K_UP) or down(pygame.K_w),
        down=down(pygame.K_DOWN) or down(pygame.K_s),
        action=down(pygame.K_SPACE),
    )


def run(
    *,
    world: World,
    body: Body,
    screen_size: Size,
    plan_move: PlanMove,
    blocks: Blocks,
    draw_body: DrawFn,
    max_frames: int | None = None,
) -> Body:
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((screen_size.w, screen_size.h))
    pygame.display.set_caption("tilebase")
    clock = pygame.time.Clock()
    frames = 0
    while max_frames is None or frames < max_frames:
        quit_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                quit_requested = True
        if quit_requested:
            break
        dt = clock.tick(60) / 1000.0
        keys = read_keys(pygame.key.get_pressed())
        frame = Frame(keys=keys, dt=dt, body=body, world=world)
        moved = move_body(world, body, plan_move(frame), blocks)
        body = moved.body
        camera = looking_at(body.rect.center, screen_size)
        screen.fill((18, 18, 24))
        view = camera.world_rect
        for cell in cells_overlapping(world, view):
            cell.draw(screen, world_to_screen(camera, cell.rect))
        draw_body(screen, world_to_screen(camera, body.rect))
        pygame.display.flip()
        frames += 1
    pygame.quit()
    return body
