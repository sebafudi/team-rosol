from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PngError:
    reason: str


def load_png(path: Path):
    """Decode an 8-bit RGBA PNG. This pygame build has no PNG loader."""
    import pygame

    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return PngError(reason="not a png")
    decoded = _rgba(data)
    if isinstance(decoded, PngError):
        return decoded
    width, height, rows = decoded
    payload = b"".join(rows)
    image = pygame.image.frombuffer(payload, (width, height), "RGBA")
    if pygame.display.get_surface() is None:
        return image
    return image.convert_alpha()


def _rgba(data: bytes):
    pos = 8
    idat = bytearray()
    header = None
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        kind = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = chunk
        elif kind == b"IDAT":
            idat.extend(chunk)
        elif kind == b"IEND":
            break
    if header is None:
        return PngError(reason="missing header")
    width, height, bit, color, comp, filt, inter = struct.unpack(">IIBBBBB", header)
    if (bit, color, comp, filt, inter) != (8, 6, 0, 0, 0):
        return PngError(reason="unsupported png")
    stride = width * 4
    inflated = zlib.decompress(bytes(idat))
    rows: list[bytes] = []
    index = 0
    previous = bytearray(stride)
    for _y in range(height):
        filter_type = inflated[index]
        index += 1
        row = bytearray(inflated[index : index + stride])
        index += stride
        _unfilter(filter_type, row, previous, 4)
        previous = row
        rows.append(bytes(row))
    return width, height, rows


def _unfilter(filter_type: int, row: bytearray, previous: bytearray, bpp: int) -> None:
    if filter_type == 0:
        return
    for x in range(len(row)):
        left = row[x - bpp] if x >= bpp else 0
        up = previous[x]
        up_left = previous[x - bpp] if x >= bpp else 0
        if filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        else:
            predictor = _paeth(left, up, up_left)
        row[x] = (row[x] + predictor) & 255


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left
