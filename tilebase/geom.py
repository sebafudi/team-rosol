from dataclasses import dataclass


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float


@dataclass(frozen=True)
class Size:
    w: int
    h: int


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def center(self) -> Vec2:
        return Vec2(self.x + self.w / 2, self.y + self.h / 2)
