"""Mesh builders. Each returns an (N, 8) float32 array: position, colour, uv.

Lighting is baked into the vertex colours per face (flat shading)."""

import numpy as np

LIGHT_DIR = np.array([0.4, 0.8, 0.45], dtype="f4")
LIGHT_DIR /= np.linalg.norm(LIGHT_DIR)
AMBIENT = 0.45

DEFAULT_UVS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def _shade(normal):
    return AMBIENT + (1.0 - AMBIENT) * max(0.0, float(np.dot(normal, LIGHT_DIR)))


def quad(p0, p1, p2, p3, color, uvs=DEFAULT_UVS):
    """Two triangles for a quad whose corners are given counter-clockwise."""
    points = [np.asarray(p, dtype="f4") for p in (p0, p1, p2, p3)]
    normal = np.cross(points[1] - points[0], points[2] - points[0])
    normal /= np.linalg.norm(normal)
    shaded = np.asarray(color, dtype="f4") * _shade(normal)
    out = np.empty((6, 8), dtype="f4")
    for row, i in enumerate((0, 1, 2, 0, 2, 3)):
        out[row, :3] = points[i]
        out[row, 3:6] = shaded
        out[row, 6:] = uvs[i]
    return out


def quad_facing(p0, p1, p2, p3, color, toward):
    """Quad wound so that its front face points along `toward`."""
    p0, p1, p2, p3 = (np.asarray(p, dtype="f4") for p in (p0, p1, p2, p3))
    if np.dot(np.cross(p1 - p0, p2 - p0), toward) < 0.0:
        p1, p3 = p3, p1
    return quad(p0, p1, p2, p3, color)


def box(size, color, base_y=0.0, bottom=False, transform=None):
    """Box centred on X/Z, sitting on `base_y`.

    `transform` is an optional 4x4 matrix applied to the corners."""
    hx, hz = size[0] / 2.0, size[2] / 2.0
    y0, y1 = base_y, base_y + size[1]
    faces = [
        ((-hx, y0, hz), (hx, y0, hz), (hx, y1, hz), (-hx, y1, hz)),      # +Z
        ((hx, y0, -hz), (-hx, y0, -hz), (-hx, y1, -hz), (hx, y1, -hz)),  # -Z
        ((hx, y0, hz), (hx, y0, -hz), (hx, y1, -hz), (hx, y1, hz)),      # +X
        ((-hx, y0, -hz), (-hx, y0, hz), (-hx, y1, hz), (-hx, y1, -hz)),  # -X
        ((-hx, y1, hz), (hx, y1, hz), (hx, y1, -hz), (-hx, y1, -hz)),    # +Y
    ]
    if bottom:
        faces.append(((-hx, y0, -hz), (hx, y0, -hz), (hx, y0, hz), (-hx, y0, hz)))
    if transform is not None:
        faces = [[(transform @ np.array([*corner, 1.0]))[:3] for corner in face]
                 for face in faces]
    return np.concatenate([quad(*face, color) for face in faces])


def translated(vertices, offset):
    """Copy of `vertices` with positions moved by `offset`."""
    out = vertices.copy()
    out[:, :3] += np.asarray(offset, dtype="f4")
    return out
