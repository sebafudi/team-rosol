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
