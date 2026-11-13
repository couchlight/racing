"""4x4 matrix helpers. Column-vector convention (M @ v), right-handed, Y up."""

import math

import numpy as np

UP = np.array([0.0, 1.0, 0.0], dtype="f4")


def perspective(fov_y_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov_y_deg) / 2.0)
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2.0 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up=UP):
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4, dtype="f4")
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def translate(x, y, z):
    m = np.identity(4, dtype="f4")
    m[:3, 3] = (x, y, z)
    return m


def rotate_y(angle):
    """Rotation about Y. Maps +Z to forward(angle)."""
    c, s = math.cos(angle), math.sin(angle)
    m = np.identity(4, dtype="f4")
    m[0, 0] = c
    m[0, 2] = s
    m[2, 0] = -s
    m[2, 2] = c
    return m


def forward(heading):
    """Unit forward vector for a heading about Y. Heading 0 faces +Z."""
    return np.array([math.sin(heading), 0.0, math.cos(heading)], dtype="f4")
