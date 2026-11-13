"""Vertex data for in-game models. Local axes: +X left, +Y up, +Z forward."""

import numpy as np

from render import primitives

WHEEL_COLOR = (0.08, 0.08, 0.08)
GLASS_COLOR = (0.15, 0.2, 0.3)


def car(color):
    parts = [
        primitives.box((1.7, 0.55, 3.8), color, base_y=0.3),
        primitives.translated(
            primitives.box((1.4, 0.45, 1.7), GLASS_COLOR, base_y=0.85), (0.0, 0.0, -0.3)),
    ]
    for x in (-0.85, 0.85):
        for z in (-1.2, 1.25):
            parts.append(primitives.translated(
                primitives.box((0.3, 0.6, 0.7), WHEEL_COLOR), (x, 0.0, z)))
    return np.concatenate(parts)
