from dataclasses import dataclass

from tilebase.geom import Rect, Size, Vec2


@dataclass(frozen=True)
class Camera:
    origin: Vec2
    screen: Size

    @property
    def world_rect(self) -> Rect:
        return Rect(self.origin.x, self.origin.y, float(self.screen.w), float(self.screen.h))


def looking_at(target: Vec2, screen: Size) -> Camera:
    return Camera(
        origin=Vec2(target.x - screen.w / 2, target.y - screen.h / 2),
        screen=screen,
    )


def world_to_screen(camera: Camera, rect: Rect) -> Rect:
    return Rect(rect.x - camera.origin.x, rect.y - camera.origin.y, rect.w, rect.h)


@dataclass(frozen=True)
class Presentation:
    camera: Size
    scale: int
    x: int
    y: int


def fit_display(display: Size, base: Size) -> Presentation:
    """Cover `display` with whole camera pixels, growing past `base` on the long axis."""
    fitted = min(display.w // base.w, display.h // base.h)
    scale = fitted if fitted >= 1 else 1
    camera = Size(display.w // scale, display.h // scale)
    return Presentation(
        camera=camera,
        scale=scale,
        x=(display.w - camera.w * scale) // 2,
        y=(display.h - camera.h * scale) // 2,
    )
