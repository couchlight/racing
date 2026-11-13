"""Arcade car.

Motion is integrated in the XZ plane in world space: the velocity vector is
separate from the heading, and lateral grip pulls the velocity back in line
with the car. Height and tilt come from the track surface under the car.
"""

import math

import numpy as np

UP = np.array([0.0, 1.0, 0.0])

# Automatic gearbox: top speed (m/s) and full-throttle acceleration per gear.
GEAR_TOP_SPEEDS = (17.0, 30.0, 43.0, 56.0, 70.0)
GEAR_ACCELERATION = (11.0, 8.5, 6.5, 4.8, 3.4)
UPSHIFT = 0.97            # shift up at this fraction of the gear's top speed
DOWNSHIFT = 0.85          # shift down below this fraction of the lower gear's top speed

BRAKING = 28.0
REVERSE_ACCELERATION = 6.0
REVERSE_MAX_SPEED = 9.0
ROLLING_DRAG = 0.4
AIR_DRAG = 0.0006         # times speed squared
ENGINE_BRAKING = 1.5      # extra deceleration off the throttle

STEER_SPEED = 5.0         # how fast the wheels follow the input, per second
MIN_TURN_RADIUS = 9.0     # limits yaw rate at low speed
MAX_LATERAL_ACCEL = 22.0  # limits yaw rate at high speed

GRIP = 10.0               # how fast sideways velocity is killed, per second
DRIFT_GRIP = 3.0          # same, while drifting
DRIFT_SLIP = 6.0          # sideways speed (m/s) above which the car is drifting
DRIFT_ENTRY_SPEED = 15.0  # braking while steering above this speed starts a drift

HALF_WIDTH = 0.9
WALL_BOUNCE = 0.3
WALL_SCRUB = 0.03         # fraction of speed lost per m/s of impact
WALL_MIN_KEEP = 0.5       # an impact never costs more than this fraction
WALL_ALIGN_RATE = 5.0     # how fast a wall turns the car back along the track


def _wrap_angle(angle):
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


class Car:
    def __init__(self, track):
        self.track = track
        self.place(0.0, 0.0)

    def place(self, s, lateral):
        """Put the car at rest on the track, facing the direction of travel."""
        point = self.track.surface(s, lateral)
        self.x, self.z = float(point[0]), float(point[2])
        self.heading = self.track.heading(s)
        self.vx = self.vz = 0.0
        self.steer = 0.0
        self.gear = 0
        self.forward_speed = 0.0
        self.s, self.lateral, self._segment = self.track.locate(self.x, self.z)

    @property
    def speed_kmh(self):
        return abs(self.forward_speed) * 3.6

    @property
    def gear_label(self):
        return "R" if self.forward_speed < -0.1 else str(self.gear + 1)

    def update(self, steer, throttle, brake, dt):
        """Advance by `dt`. steer is -1..1 (positive right), throttle and brake 0..1."""
        step = STEER_SPEED * dt
        self.steer += max(-step, min(step, steer - self.steer))

        # Forward and right unit vectors in the XZ plane.
        fx, fz = math.sin(self.heading), math.cos(self.heading)
        rx, rz = -fz, fx
        v_long = self.vx * fx + self.vz * fz
        v_lat = self.vx * rx + self.vz * rz

        last_gear = len(GEAR_TOP_SPEEDS) - 1
        if self.gear < last_gear and v_long > GEAR_TOP_SPEEDS[self.gear] * UPSHIFT:
            self.gear += 1
        elif self.gear > 0 and v_long < GEAR_TOP_SPEEDS[self.gear - 1] * DOWNSHIFT:
            self.gear -= 1

        if throttle > 0.0:
            if v_long < 0.0:
                v_long = min(0.0, v_long + BRAKING * throttle * dt)
            elif v_long < GEAR_TOP_SPEEDS[self.gear]:
                v_long += GEAR_ACCELERATION[self.gear] * throttle * dt
        if brake > 0.0:
            if v_long > 0.0:
                v_long = max(0.0, v_long - BRAKING * brake * dt)
            elif throttle == 0.0:
                v_long = max(-REVERSE_MAX_SPEED, v_long - REVERSE_ACCELERATION * brake * dt)

        drag = ROLLING_DRAG + AIR_DRAG * v_long * v_long
        if throttle == 0.0:
            drag += ENGINE_BRAKING
        if v_long > 0.0:
            v_long = max(0.0, v_long - drag * dt)
        elif v_long < 0.0:
            v_long = min(0.0, v_long + drag * dt)

        drifting = abs(v_lat) > DRIFT_SLIP or (
            brake > 0.5 and abs(self.steer) > 0.5 and v_long > DRIFT_ENTRY_SPEED)
        v_lat *= math.exp(-(DRIFT_GRIP if drifting else GRIP) * dt)

        self.vx = fx * v_long + rx * v_lat
        self.vz = fz * v_long + rz * v_lat
        self.forward_speed = v_long

        # Positive steer is right, which is a decreasing heading.
        speed = abs(v_long)
        yaw_rate = self.steer * min(speed / MIN_TURN_RADIUS,
                                    MAX_LATERAL_ACCEL / max(speed, 1.0))
        self.heading -= yaw_rate * dt * (1.0 if v_long >= 0.0 else -1.0)

        self.x += self.vx * dt
        self.z += self.vz * dt

        self.s, self.lateral, self._segment = self.track.locate(
            self.x, self.z, self._segment)
        self._collide_with_walls(dt)

    def _collide_with_walls(self, dt):
        limit = self.track.half_width - HALF_WIDTH
        if abs(self.lateral) <= limit:
            return
        side = 1.0 if self.lateral > 0.0 else -1.0
        _, _, right, _ = self.track.frame(self.s)

        # Push back inside.
        push = side * limit - self.lateral
        self.x += right[0] * push
        self.z += right[2] * push
        self.lateral = side * limit

        # Remove the velocity going into the wall, with a small bounce.
        into_wall = (self.vx * right[0] + self.vz * right[2]) * side
        if into_wall > 0.0:
            self.vx -= right[0] * side * into_wall * (1.0 + WALL_BOUNCE)
            self.vz -= right[2] * side * into_wall * (1.0 + WALL_BOUNCE)
            keep = max(WALL_MIN_KEEP, 1.0 - WALL_SCRUB * into_wall)
            self.vx *= keep
            self.vz *= keep

        # Turn the nose back along the track so the car cannot wedge itself.
        error = _wrap_angle(self.track.heading(self.s) - self.heading)
        self.heading += error * min(1.0, WALL_ALIGN_RATE * dt)

    def shift_lateral(self, amount):
        """Move sideways across the track by `amount` metres (positive right)."""
        _, _, right, _ = self.track.frame(self.s)
        self.x += right[0] * amount
        self.z += right[2] * amount
        self.lateral += amount

    def scale_speed(self, factor):
        self.vx *= factor
        self.vz *= factor
        self.forward_speed *= factor

    def pose(self):
        """(position, forward, up) on the road surface."""
        position = self.track.surface(self.s, self.lateral)
        position[0], position[2] = self.x, self.z
        _, _, normal = self.track.orientation(self.s)
        fx, fz = math.sin(self.heading), math.cos(self.heading)
        # Tilt the flat heading so it lies in the road plane.
        forward = np.array([fx, -(fx * normal[0] + fz * normal[2]) / normal[1], fz])
        return position, forward / np.linalg.norm(forward), normal
