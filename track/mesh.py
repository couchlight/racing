"""Builds the renderable geometry for a Track."""

import math

import numpy as np

from render import primitives
from render.matrices import frame_matrix

UP = np.array([0.0, 1.0, 0.0])

ROAD_STRIPS = 4            # quads across the asphalt (limits affine warping)
WALL_HEIGHT = 1.2
VERGE_WIDTH = 12.0         # grass strip outside each wall
VERGE_DROP = 1.0           # how far the verge's outer edge sits below the centreline
SKIRT_DEPTH = 4.0
TERRAIN_CELL = 16.0
TERRAIN_DROP = 2.5         # terrain sits this far below the centreline near the road
TERRAIN_MARGIN = 250.0     # terrain built this far beyond the track's bounds
TERRAIN_VISIBLE = 250.0    # cells further than this from the road are skipped
HILL_START = 25.0          # distance from the road where the terrain starts to rise
HILL_SLOPE = 0.07
GANTRY_HEIGHT = 6.0

ASPHALT = (1.0, 1.0, 1.0)
KERB_COLORS = ((0.85, 0.1, 0.1), (0.9, 0.9, 0.9))
WALL_COLORS = ((0.75, 0.75, 0.8), (0.2, 0.3, 0.7))
WALL_BACK = (0.3, 0.3, 0.35)
VERGE_COLORS = ((0.2, 0.5, 0.18), (0.24, 0.56, 0.2))
SKIRT_COLOR = (0.12, 0.3, 0.1)
TERRAIN_COLOR = np.array([0.22, 0.5, 0.2])
START_COLORS = ((0.95, 0.95, 0.95), (0.08, 0.08, 0.08))
START_GANTRY = (0.9, 0.9, 0.9)
CHECKPOINT_GANTRY = (0.95, 0.75, 0.1)


def road_texture():
    """32x32 asphalt tile: edge lines and a dashed centre line.

    U runs across the full road width, V along it (one tile per two samples)."""
    rng = np.random.default_rng(3)
    tile = rng.integers(60, 85, size=(32, 32, 1), dtype="u1").repeat(3, axis=2)
    tile[:, 1] = tile[:, 30] = 215          # edge lines
    tile[:16, 15:17] = 215                  # centre dash
    return tile


def _edge(track, i, lateral):
    """Road-surface point at sample `i`, `lateral` metres right of centre."""
    return (track.centers[i] + track.rights[i] * lateral
            + UP * (lateral * math.tan(track.banks[i])))


def _road(track):
    quads = []
    hw = track.road_half_width
    laterals = np.linspace(-hw, hw, ROAD_STRIPS + 1)
    for i in range(track.n):
        j = (i + 1) % track.n
        v0, v1 = i * 0.5, (i + 1) * 0.5
        for k in range(ROAD_STRIPS):
            u0, u1 = k / ROAD_STRIPS, (k + 1) / ROAD_STRIPS
            quads.append(primitives.quad(
                _edge(track, i, laterals[k]), _edge(track, i, laterals[k + 1]),
                _edge(track, j, laterals[k + 1]), _edge(track, j, laterals[k]),
                ASPHALT, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))))
    return np.concatenate(quads)


def _trackside(track):
    """Kerbs, walls, verges and the skirt under each verge."""
    quads = []
    road_hw, hw = track.road_half_width, track.half_width
    for i in range(track.n):
        j = (i + 1) % track.n
        for side in (-1.0, 1.0):
            outward_i = track.rights[i] * side
            outward_j = track.rights[j] * side

            # Kerb: asphalt edge to wall. Corners go left-rear, right-rear,
            # right-front, left-front so the face points up.
            inner, outer = sorted((side * road_hw, side * hw))
            quads.append(primitives.quad(
                _edge(track, i, inner), _edge(track, i, outer),
                _edge(track, j, outer), _edge(track, j, inner),
                KERB_COLORS[i % 2]))

            # Wall, both faces.
            base_i, base_j = _edge(track, i, side * hw), _edge(track, j, side * hw)
            top_i, top_j = base_i + UP * WALL_HEIGHT, base_j + UP * WALL_HEIGHT
            quads.append(primitives.quad_facing(
                base_i, base_j, top_j, top_i, WALL_COLORS[(i // 2) % 2], -outward_i))
            quads.append(primitives.quad_facing(
                base_i, base_j, top_j, top_i, WALL_BACK, outward_i))

            # Verge: from the wall base out and slightly down.
            verge_i = track.centers[i] + outward_i * (hw + VERGE_WIDTH) - UP * VERGE_DROP
            verge_j = track.centers[j] + outward_j * (hw + VERGE_WIDTH) - UP * VERGE_DROP
            quads.append(primitives.quad_facing(
                base_i, base_j, verge_j, verge_i, VERGE_COLORS[i % 2], UP))

            # Skirt: closes the gap between the verge edge and the terrain.
            quads.append(primitives.quad_facing(
                verge_i, verge_j, verge_j - UP * SKIRT_DEPTH, verge_i - UP * SKIRT_DEPTH,
                SKIRT_COLOR, outward_i))
    return np.concatenate(quads)


def _terrain(track, rng):
    """Height-field around the track: follows the road's elevation nearby and
    rises into low hills further out."""
    xz = track.centers[:, [0, 2]]
    low = xz.min(axis=0) - TERRAIN_MARGIN
    high = xz.max(axis=0) + TERRAIN_MARGIN
    xs = np.arange(low[0], high[0] + TERRAIN_CELL, TERRAIN_CELL)
    zs = np.arange(low[1], high[1] + TERRAIN_CELL, TERRAIN_CELL)
    grid_x, grid_z = np.meshgrid(xs, zs, indexing="ij")
    points = np.stack([grid_x.ravel(), grid_z.ravel()], axis=1)

    dist2 = ((points[:, None, :] - xz[None, :, :]) ** 2).sum(axis=2)
    dist = np.sqrt(dist2.min(axis=1))
    # Blend the elevation of nearby track samples (inverse-distance weighted).
    weights = 1.0 / (dist2 + 25.0) ** 2
    height = (weights * track.centers[:, 1]).sum(axis=1) / weights.sum(axis=1)

    beyond = np.maximum(0.0, dist - HILL_START)
    height += -TERRAIN_DROP + beyond * HILL_SLOPE
    height += rng.uniform(-1.5, 1.5, size=len(height)) * np.minimum(1.0, beyond / 30.0)

    height = height.reshape(grid_x.shape)
    dist = dist.reshape(grid_x.shape)

    quads = []
    for ix in range(len(xs) - 1):
        for iz in range(len(zs) - 1):
            if dist[ix:ix + 2, iz:iz + 2].min() > TERRAIN_VISIBLE:
                continue
            x0, x1, z0, z1 = xs[ix], xs[ix + 1], zs[iz], zs[iz + 1]
            quads.append(primitives.quad(
                (x0, height[ix, iz + 1], z1), (x1, height[ix + 1, iz + 1], z1),
                (x1, height[ix + 1, iz], z0), (x0, height[ix, iz], z0),
                TERRAIN_COLOR * rng.uniform(0.85, 1.1)))
    return np.concatenate(quads)


def _start_line(track):
    """Two rows of checkers across the road at s = 0."""
    quads = []
    columns, row_length, lift = 14, 1.0, 0.04
    hw = track.road_half_width
    laterals = np.linspace(-hw, hw, columns + 1)
    for row in range(2):
        s0, s1 = row * row_length, (row + 1) * row_length
        for col in range(columns):
            corners = [track.surface(s, lat) + UP * lift for s, lat in (
                (s0, laterals[col]), (s0, laterals[col + 1]),
                (s1, laterals[col + 1]), (s1, laterals[col]))]
            quads.append(primitives.quad(*corners, START_COLORS[(row + col) % 2]))
    return np.concatenate(quads)


def _gantry(track, s, color):
    """Two posts and a beam spanning the track at distance `s`."""
    center, tangent, right, _ = track.frame(s)
    forward = np.array([tangent[0], 0.0, tangent[2]])
    forward /= np.linalg.norm(forward)
    span = track.half_width + 1.0
    parts = []
    for side in (-1.0, 1.0):
        base = center + right * (side * span) - UP * 1.5
        parts.append(primitives.box(
            (0.8, GANTRY_HEIGHT + 1.5, 0.8), color,
            transform=frame_matrix(-right, UP, forward, base)))
    parts.append(primitives.box(
        (span * 2.0 + 0.8, 1.2, 0.8), color, bottom=True,
        transform=frame_matrix(-right, UP, forward, center + UP * GANTRY_HEIGHT)))
    return np.concatenate(parts)


def build(track, renderer, checkpoints, seed):
    """Create the track's meshes. `checkpoints` are distances along the track;
    the first is the start line. Returns a list of meshes to draw."""
    rng = np.random.default_rng(seed)
    static = [_trackside(track), _terrain(track, rng), _start_line(track)]
    for index, s in enumerate(checkpoints):
        static.append(_gantry(track, s, START_GANTRY if index == 0 else CHECKPOINT_GANTRY))
    return [
        renderer.mesh(_road(track), renderer.texture(road_texture())),
        renderer.mesh(np.concatenate(static)),
    ]
