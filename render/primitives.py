"""Mesh builders. Each returns an (N, 8) float32 array: position, colour, uv.

Lighting is baked into the vertex colours per face (flat shading)."""

import numpy as np

LIGHT_DIR = np.array([0.4, 0.8, 0.45], dtype="f4")
LIGHT_DIR /= np.linalg.norm(LIGHT_DIR)
AMBIENT = 0.45


def _shade(normal):
    return AMBIENT + (1.0 - AMBIENT) * max(0.0, float(np.dot(normal, LIGHT_DIR)))


def quad(p0, p1, p2, p3, color, uv_scale=(1.0, 1.0)):
    """Two triangles for a quad whose corners are given counter-clockwise."""
    p0, p1, p2, p3 = (np.asarray(p, dtype="f4") for p in (p0, p1, p2, p3))
    normal = np.cross(p1 - p0, p2 - p0)
    normal /= np.linalg.norm(normal)
    shaded = np.asarray(color, dtype="f4") * _shade(normal)
    u, v = uv_scale
    corners = ((p0, (0.0, 0.0)), (p1, (u, 0.0)), (p2, (u, v)), (p3, (0.0, v)))
    rows = [np.concatenate([corners[i][0], shaded, corners[i][1]])
            for i in (0, 1, 2, 0, 2, 3)]
    return np.array(rows, dtype="f4")


def box(size, color, base_y=0.0):
    """Axis-aligned box centred on X/Z, sitting on `base_y`."""
    hx, hz = size[0] / 2.0, size[2] / 2.0
    y0, y1 = base_y, base_y + size[1]
    faces = (
        ((-hx, y0, hz), (hx, y0, hz), (hx, y1, hz), (-hx, y1, hz)),      # +Z
        ((hx, y0, -hz), (-hx, y0, -hz), (-hx, y1, -hz), (hx, y1, -hz)),  # -Z
        ((hx, y0, hz), (hx, y0, -hz), (hx, y1, -hz), (hx, y1, hz)),      # +X
        ((-hx, y0, -hz), (-hx, y0, hz), (-hx, y1, hz), (-hx, y1, -hz)),  # -X
        ((-hx, y1, hz), (hx, y1, hz), (hx, y1, -hz), (-hx, y1, -hz)),    # +Y
    )
    return np.concatenate([quad(*face, color) for face in faces])


def ground(cells, cell_size, color=(1.0, 1.0, 1.0)):
    """Flat grid of quads centred on the origin, one texture repeat per cell.

    Kept tessellated on purpose: affine texturing warps badly on large polygons."""
    half = cells * cell_size / 2.0
    quads = []
    for iz in range(cells):
        for ix in range(cells):
            x0 = ix * cell_size - half
            z0 = iz * cell_size - half
            x1, z1 = x0 + cell_size, z0 + cell_size
            quads.append(quad((x0, 0.0, z1), (x1, 0.0, z1),
                              (x1, 0.0, z0), (x0, 0.0, z0), color))
    return np.concatenate(quads)


def translated(vertices, offset):
    """Copy of `vertices` with positions moved by `offset`."""
    out = vertices.copy()
    out[:, :3] += np.asarray(offset, dtype="f4")
    return out
