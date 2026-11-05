from __future__ import annotations

import os
from typing import Protocol

os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

from tilebase.geom import Size
from tilebase.move import Blocks, Body, Frame, Keys, PlanMove, move_body
from tilebase.tiles import DrawFn, World, cells_overlapping
from tilebase.view import Presentation, fit_display, looking_at, world_to_screen

BACKDROP = (18, 18, 24)


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


def wants_quit(event) -> bool:
    import pygame

    return event.type == pygame.QUIT or (
        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
    )


def open_fullscreen(base: Size):
    """Open a desktop fullscreen window and a camera canvas that covers it."""
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption("tilebase")
    display = Size(screen.get_width(), screen.get_height())
    fitted = fit_display(display, base)
    canvas = pygame.Surface((fitted.camera.w, fitted.camera.h)).convert()
    return screen, canvas, fitted


def present(screen, canvas, fitted: Presentation) -> None:
    import pygame

    screen.fill(BACKDROP)
    screen.blit(pygame.transform.scale_by(canvas, fitted.scale), (fitted.x, fitted.y))


def run(
    *,
    world: World,
    body: Body,
    screen_size: Size,
    plan_move: PlanMove,
    blocks: Blocks,
    draw_body: DrawFn,
    max_frames: int | None = None,
    window: tuple | None = None,
) -> Body:
    import pygame

    if window is None:
        screen, canvas, fitted = open_fullscreen(screen_size)
    else:
        screen, canvas, fitted = window
    clock = pygame.time.Clock()
    frames = 0
    while max_frames is None or frames < max_frames:
        quit_requested = False
        for event in pygame.event.get():
            if wants_quit(event):
                quit_requested = True
        if quit_requested:
            break
        dt = clock.tick(60) / 1000.0
        keys = read_keys(pygame.key.get_pressed())
        frame = Frame(keys=keys, dt=dt, body=body, world=world)
        moved = move_body(world, body, plan_move(frame), blocks)
        body = moved.body
        camera = looking_at(body.rect.center, fitted.camera)
        canvas.fill(BACKDROP)
        view = camera.world_rect
        for cell in cells_overlapping(world, view):
            cell.draw(canvas, world_to_screen(camera, cell.rect))
        draw_body(canvas, world_to_screen(camera, body.rect))
        present(screen, canvas, fitted)
        pygame.display.flip()
        frames += 1
    pygame.quit()
    return body
