"""Computer-controlled cars. They run in track space: a distance along the
track and a lateral offset, following a speed limit derived from curvature."""

import math

import numpy as np

LATERAL_ACCEL = 17.0      # cornering limit used for the speed profile
BRAKING = 14.0
TOP_SPEED = 64.0
ACCELERATION = 9.0        # at standstill, tapering towards top speed
MIN_ACCELERATION = 1.5
LANE_CHANGE_RATE = 3.0    # lateral metres per second


def speed_limits(track):
    """Per-sample speed limit: cornering speed, lowered ahead of each corner
    so it can be reached under braking."""
    limits = np.minimum(TOP_SPEED, np.sqrt(
        LATERAL_ACCEL / np.maximum(np.abs(track.curvature), 1e-6)))
    for _ in range(2):   # twice round, so braking zones wrap past the start line
        for i in range(track.n - 1, -1, -1):
            ahead = limits[(i + 1) % track.n]
            limits[i] = min(limits[i], math.sqrt(ahead ** 2 + 2.0 * BRAKING * track.spacing))
    return limits


class Opponent:
    def __init__(self, track, limits, distance, lateral, skill):
        """`distance` is unwrapped (negative behind the start line).
        `skill` scales the speed limits, 1.0 being the fastest line."""
        self.track = track
        self.limits = limits
        self.distance = distance
        self.lateral = lateral
        self.lane = lateral       # lateral offset being steered towards
        self.skill = skill
        self.speed = 0.0

    @property
    def s(self):
        return self.distance % self.track.length

    def update(self, dt, blocked_speed=None):
        """`blocked_speed` is the speed of a car directly ahead, if any."""
        index = int(self.s / self.track.spacing) % self.track.n
        target = self.limits[index] * self.skill
        if blocked_speed is not None:
            target = min(target, blocked_speed)

        if self.speed < target:
            accel = ACCELERATION * (1.0 - self.speed / TOP_SPEED) + MIN_ACCELERATION
            self.speed = min(target, self.speed + accel * dt)
        else:
            self.speed = max(target, self.speed - BRAKING * dt)

        self.distance += self.speed * dt
        step = LANE_CHANGE_RATE * dt
        self.lateral += max(-step, min(step, self.lane - self.lateral))

    def pose(self):
        """(position, forward, up) on the road surface."""
        tangent, _, normal = self.track.orientation(self.s)
        return self.track.surface(self.s, self.lateral), tangent, normal
