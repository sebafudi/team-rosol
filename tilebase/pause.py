"""Esc pause menu shared by every level: resume, restart, main menu, quit.

The level loop stops ticking while paused and asks `pause_key` what a key
press means. It draws the menu with `draw_pause` on top of the frozen frame.
"""

from __future__ import annotations

from tilebase.geom import Rect

ITEMS = (
    ("resume", "RESUME"),
    ("restart", "RESTART"),
    ("menu", "MAIN MENU"),
    ("quit", "QUIT"),
)
SCALE = 2
GOLD = (250, 204, 72)


def pause_key(key: int, picked: int) -> tuple[int, str | None]:
    """The new highlight, and the chosen item id once one is picked."""
    import pygame

    if key == pygame.K_ESCAPE:
        return picked, "resume"
    if key in (pygame.K_UP, pygame.K_w):
        return (picked - 1) % len(ITEMS), None
    if key in (pygame.K_DOWN, pygame.K_s):
        return (picked + 1) % len(ITEMS), None
    if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
        return picked, ITEMS[picked][0]
    return picked, None


def draw_pause(screen: object, picked: int) -> None:
    """Dim the frame and put the stone sign with the choices in the middle."""
    import pygame

    from tilebase.art import source_image
    from tilebase.play import _ink
    from tilebase.title import stone_sign

    width, height = screen.get_size()
    shade = pygame.Surface((width, height), pygame.SRCALPHA)
    shade.fill((10, 8, 20, 150))
    screen.blit(shade, (0, 0))

    def text_w(text: str) -> int:
        return (len(text) * 6 - 1) * SCALE

    labels = [("> " if i == picked else "  ") + label for i, (_id, label) in enumerate(ITEMS)]
    glyph_h = 7 * SCALE
    line = glyph_h + 6 * SCALE
    pad = 10 * SCALE
    w = max(text_w("PAUSED"), *(text_w(t) for t in labels)) + pad * 2
    h = pad * 2 + glyph_h + 8 * SCALE + line * len(labels)
    x = (width - w) // 2
    y = (height - h) // 2
    stone_sign(screen, Rect(x, y, w, h), source_image("tiles", "solid.png"))
    _ink(screen, "PAUSED", x + (w - text_w("PAUSED")) // 2, y + pad, SCALE)
    top = y + pad + glyph_h + 8 * SCALE
    for i, label in enumerate(labels):
        ry = top + i * line
        if i == picked:
            pygame.draw.rect(
                screen, GOLD, (x + pad // 2, ry - 3 * SCALE, w - pad, line - 2 * SCALE)
            )
        _ink(screen, label, x + pad, ry, SCALE)
