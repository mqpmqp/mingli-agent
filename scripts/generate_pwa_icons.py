from __future__ import annotations

import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_DIRECTORY = ROOT / "web" / "pwa" / "public" / "icons"
BACKGROUND = (23, 63, 56)
IVORY = (243, 240, 232)
GOLD = (183, 139, 66)


def _chunk(name: bytes, payload: bytes) -> bytes:
    body = name + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _pixel(size: int, x: float, y: float) -> tuple[int, int, int]:
    center = size / 2
    radius = size * 0.35
    dx = x - center
    dy = y - center
    if dx * dx + dy * dy > radius * radius:
        return BACKGROUND

    upper_center = center - radius / 2
    lower_center = center + radius / 2
    inner_radius = radius / 2
    gold = dx >= 0
    if dx * dx + (y - upper_center) ** 2 <= inner_radius * inner_radius:
        gold = False
    if dx * dx + (y - lower_center) ** 2 <= inner_radius * inner_radius:
        gold = True

    dot_radius = radius * 0.115
    if dx * dx + (y - upper_center) ** 2 <= dot_radius * dot_radius:
        return BACKGROUND
    if dx * dx + (y - lower_center) ** 2 <= dot_radius * dot_radius:
        return IVORY
    return GOLD if gold else IVORY


def _png_bytes(size: int) -> bytes:
    samples = 4
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            totals = [0, 0, 0]
            for sample_y in range(samples):
                for sample_x in range(samples):
                    color = _pixel(
                        size,
                        x + (sample_x + 0.5) / samples,
                        y + (sample_y + 0.5) / samples,
                    )
                    for channel, value in enumerate(color):
                        totals[channel] += value
            rows.extend(round(total / (samples * samples)) for total in totals)

    signature = b"\x89PNG\r\n\x1a\n"
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return signature + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + _chunk(b"IEND", b"")


def main() -> None:
    ICON_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for filename, size in (
        ("icon-192.png", 192),
        ("icon-512.png", 512),
        ("apple-touch-icon-180.png", 180),
    ):
        (ICON_DIRECTORY / filename).write_bytes(_png_bytes(size))


if __name__ == "__main__":
    main()
