"""Procedural closed-loop track from a seed.

The centreline is a circle whose radius is modulated by a few random
harmonics, r(theta) = R * (1 + sum a_k cos(k theta + phi_k)). A polar curve
like this cannot cross itself, which keeps projection onto the track
unambiguous. Harmonic amplitudes are scaled down until the tightest corner
is driveable.
"""

import numpy as np

from track.track import Track

BASE_RADIUS = 230.0
HALF_WIDTH = 8.0          # centreline to wall
ROAD_HALF_WIDTH = 7.0     # centreline to kerb
SPACING = 5.0             # distance between centreline samples
MIN_CORNER_RADIUS = 38.0
HARMONICS = (2, 3, 4, 5, 6)
ELEVATION = (9.0, 5.0, 3.0)   # amplitude of 1, 2 and 3 cycles per lap
DENSE_SAMPLES = 4000


def _min_radius(x, z):
    """Smallest radius of curvature of a dense closed polyline."""
    dx = (np.roll(x, -1) - np.roll(x, 1)) / 2.0
    dz = (np.roll(z, -1) - np.roll(z, 1)) / 2.0
    ddx = np.roll(x, -1) - 2.0 * x + np.roll(x, 1)
    ddz = np.roll(z, -1) - 2.0 * z + np.roll(z, 1)
    curvature = np.abs(dx * ddz - dz * ddx) / (dx * dx + dz * dz) ** 1.5
    return 1.0 / curvature.max()


def _straightest_index(track, behind=14, ahead=24):
    """Sample index with the least curvature around it (for the start line)."""
    bend = np.abs(track.curvature)
    worst = np.full(track.n, 0.0)
    for offset in range(-behind, ahead + 1):
        worst = np.maximum(worst, np.roll(bend, -offset))
    return int(worst.argmin())


def generate(seed):
    rng = np.random.default_rng(seed)
    amplitudes = np.array([rng.uniform(0.06, 0.2) / (k / 2.0) ** 0.8 for k in HARMONICS])
    phases = rng.uniform(0.0, 2.0 * np.pi, size=len(HARMONICS))
    theta = np.linspace(0.0, 2.0 * np.pi, DENSE_SAMPLES, endpoint=False)

    while True:
        radius = BASE_RADIUS * (1.0 + sum(
            a * np.cos(k * theta + p) for a, k, p in zip(amplitudes, HARMONICS, phases)))
        x = radius * np.cos(theta)
        z = radius * np.sin(theta)
        if _min_radius(x, z) >= MIN_CORNER_RADIUS:
            break
        amplitudes *= 0.92

    # Resample at even arc length.
    step = np.hypot(np.roll(x, -1) - x, np.roll(z, -1) - z)
    arc = np.concatenate([[0.0], np.cumsum(step)])
    count = int(round(arc[-1] / SPACING))
    targets = np.arange(count) * arc[-1] / count
    x = np.interp(targets, arc, np.append(x, x[0]))
    z = np.interp(targets, arc, np.append(z, z[0]))

    # Elevation: a few sine waves per lap, so it joins up at the start line.
    u = np.arange(count) / count
    y = sum(rng.uniform(0.5, 1.0) * height
            * np.sin(2.0 * np.pi * (cycles * u + rng.uniform()))
            for cycles, height in enumerate(ELEVATION, start=1))

    centers = np.stack([x, y, z], axis=1)
    track = Track(centers, HALF_WIDTH, ROAD_HALF_WIDTH)

    # Put the start line (sample 0) on the straightest part of the lap.
    start = _straightest_index(track)
    return Track(np.roll(centers, -start, axis=0), HALF_WIDTH, ROAD_HALF_WIDTH)
