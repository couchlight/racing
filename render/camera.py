import numpy as np

from render.matrices import UP, forward, look_at, perspective


class Camera:
    """Perspective camera with a chase mode."""

    def __init__(self, aspect, fov_y_deg=60.0, near=0.2, far=120.0):
        self.projection = perspective(fov_y_deg, aspect, near, far)
        self.position = np.array([0.0, 3.0, -8.0], dtype="f4")
        self.target = np.zeros(3, dtype="f4")

        # Chase parameters
        self.distance = 7.0     # behind the target
        self.height = 2.6       # above the target
        self.look_ahead = 4.0   # aim point in front of the target
        self.stiffness = 6.0    # higher = snappier follow

    def view(self):
        return look_at(self.position, self.target)

    def follow(self, target_pos, heading, dt):
        """Ease towards a point behind and above a target facing `heading`."""
        fwd = forward(heading)
        desired = target_pos - fwd * self.distance + UP * self.height
        self.position += (desired - self.position) * min(1.0, self.stiffness * dt)
        self.target = target_pos + fwd * self.look_ahead

    def snap(self, target_pos, heading):
        """Jump straight to the chase position (no easing)."""
        self.position = (target_pos - forward(heading) * self.distance
                         + UP * self.height).astype("f4")
        self.target = target_pos + forward(heading) * self.look_ahead
