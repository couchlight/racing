"""Closed-loop track described by evenly spaced centreline samples.

Conventions (shared with render.matrices): Y up, heading 0 faces +Z, and
`right` for a direction of travel is cross(forward, up). Lateral offsets are
positive to the right of the direction of travel.
"""

import math

import numpy as np

UP = np.array([0.0, 1.0, 0.0])

BANK_GAIN = 6.0      # radians of bank per unit of curvature (1 / metres)
MAX_BANK = 0.2       # radians


def _smooth(values, passes=3):
    """Circular moving average."""
    for _ in range(passes):
        values = (np.roll(values, 1) + values + np.roll(values, -1)) / 3.0
    return values


class Track:
    def __init__(self, centers, half_width, road_half_width):
        """`centers` is an (N, 3) loop of points evenly spaced in the XZ plane.

        half_width:      centreline to wall
        road_half_width: centreline to the edge of the asphalt (kerbs fill the rest)
        """
        self.centers = np.asarray(centers, dtype="f8")
        self.n = len(self.centers)
        self.half_width = half_width
        self.road_half_width = road_half_width

        nxt = np.roll(self.centers, -1, axis=0)
        prv = np.roll(self.centers, 1, axis=0)

        delta = nxt - prv
        self.tangents = delta / np.linalg.norm(delta, axis=1)[:, None]

        flat = delta.copy()
        flat[:, 1] = 0.0
        flat /= np.linalg.norm(flat, axis=1)[:, None]
        # cross(flat, UP)
        self.rights = np.stack(
            [-flat[:, 2], np.zeros(self.n), flat[:, 0]], axis=1)

        segments = nxt - self.centers
        self.length = float(np.hypot(segments[:, 0], segments[:, 2]).sum())
        self.spacing = self.length / self.n

        # Signed curvature (1 / radius), positive when turning right.
        turn = (np.roll(flat, -1, axis=0) - np.roll(flat, 1, axis=0)) / (2.0 * self.spacing)
        self.curvature = _smooth((turn * self.rights).sum(axis=1))

        # Bank angle: positive raises the right-hand side. The outside of
        # each corner is raised.
        self.banks = _smooth(-np.clip(self.curvature * BANK_GAIN, -MAX_BANK, MAX_BANK))

        self._xz = self.centers[:, [0, 2]]
        self._seg = np.roll(self._xz, -1, axis=0) - self._xz
        self._seg_len2 = (self._seg ** 2).sum(axis=1)

    def _index(self, s):
        f = (s % self.length) / self.spacing
        i = int(f) % self.n
        return i, (i + 1) % self.n, f - int(f)

    def frame(self, s):
        """(centre, tangent, right, bank) at distance `s` along the track.

        `tangent` follows the slope; `right` is horizontal."""
        i, j, t = self._index(s)
        center = self.centers[i] + (self.centers[j] - self.centers[i]) * t
        tangent = self.tangents[i] + (self.tangents[j] - self.tangents[i]) * t
        right = self.rights[i] + (self.rights[j] - self.rights[i]) * t
        bank = self.banks[i] + (self.banks[j] - self.banks[i]) * t
        return (center, tangent / np.linalg.norm(tangent),
                right / np.linalg.norm(right), bank)

    def surface(self, s, lateral):
        """Point on the road surface at distance `s`, `lateral` metres right of centre."""
        center, _, right, bank = self.frame(s)
        return center + right * lateral + UP * (lateral * math.tan(bank))

    def orientation(self, s):
        """(tangent, banked right, surface normal) at distance `s`."""
        _, tangent, right, bank = self.frame(s)
        banked_right = right * math.cos(bank) + UP * math.sin(bank)
        normal = np.cross(banked_right, tangent)
        return tangent, banked_right, normal / np.linalg.norm(normal)

    def heading(self, s):
        """Heading of the direction of travel at distance `s`."""
        _, tangent, _, _ = self.frame(s)
        return math.atan2(tangent[0], tangent[2])

    def curvature_at(self, s):
        i, j, t = self._index(s)
        return self.curvature[i] + (self.curvature[j] - self.curvature[i]) * t

    def wrap(self, delta):
        """Shortest signed distance for a difference of two `s` values."""
        return (delta + self.length / 2.0) % self.length - self.length / 2.0

    def locate(self, x, z, hint=None, window=8):
        """Project a world XZ position onto the track.

        Returns (s, lateral, segment index). `hint` is the segment index from
        the previous call; without it every segment is searched."""
        if hint is None:
            idx = np.arange(self.n)
        else:
            idx = (hint + np.arange(-window, window + 1)) % self.n
        p = np.array([x, z])
        a = self._xz[idx]
        ab = self._seg[idx]
        t = np.clip(((p - a) * ab).sum(axis=1) / self._seg_len2[idx], 0.0, 1.0)
        closest = a + ab * t[:, None]
        k = int(((p - closest) ** 2).sum(axis=1).argmin())
        i = int(idx[k])
        j = (i + 1) % self.n
        right = self.rights[i] + (self.rights[j] - self.rights[i]) * t[k]
        right_xz = right[[0, 2]] / np.hypot(right[0], right[2])
        lateral = float(np.dot(p - closest[k], right_xz))
        return ((i + float(t[k])) * self.spacing) % self.length, lateral, i
