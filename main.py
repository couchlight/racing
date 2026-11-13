import math

import numpy as np
import pygame

from controls.input_state import InputManager
from render import primitives
from render.camera import Camera
from render.matrices import forward, rotate_y, translate
from render.renderer import Renderer
from render.window import create_window
from version import get_version

WINDOW_SIZE = (960, 720)
TITLE = "Racing"

# Placeholder test scene and driving model — replaced by the procedural
# track (phase 4) and the car (phase 5).
GROUND_CELLS = 48
GROUND_CELL_SIZE = 5.0
SPAWN_CLEAR_RADIUS = 15.0
MAX_SPEED = 40.0      # units per second
ACCELERATION = 18.0
BRAKING = 35.0
DRAG = 4.0            # deceleration when coasting
TURN_RATE = 1.8       # radians per second at full steer


def make_ground_texture():
    """16x16 noisy asphalt tile with a light edge, so the affine warp is visible."""
    rng = np.random.default_rng(1)
    tile = rng.integers(70, 100, size=(16, 16, 1), dtype="u1").repeat(3, axis=2)
    tile[0, :] = tile[:, 0] = 130
    return tile


def make_scenery():
    """Randomly scattered boxes, kept clear of the spawn point."""
    rng = np.random.default_rng(7)
    boxes = []
    while len(boxes) < 120:
        x, z = rng.uniform(-110.0, 110.0, size=2)
        if math.hypot(x, z) < SPAWN_CLEAR_RADIUS:
            continue
        size = (rng.uniform(1.5, 5.0), rng.uniform(1.0, 9.0), rng.uniform(1.5, 5.0))
        color = rng.uniform(0.35, 1.0, size=3)
        boxes.append(primitives.translated(primitives.box(size, color), (x, 0.0, z)))
    return np.concatenate(boxes)


def make_car():
    body = primitives.box((1.7, 0.6, 3.6), (0.9, 0.15, 0.1), base_y=0.25)
    cabin = primitives.translated(
        primitives.box((1.4, 0.5, 1.6), (0.15, 0.2, 0.3), base_y=0.85),
        (0.0, 0.0, -0.3))
    return np.concatenate([body, cabin])


def main():
    pygame.init()
    ctx = create_window(WINDOW_SIZE, f"{TITLE} {get_version()}")
    renderer = Renderer(ctx)
    camera = Camera(aspect=WINDOW_SIZE[0] / WINDOW_SIZE[1])

    ground = renderer.mesh(
        primitives.ground(GROUND_CELLS, GROUND_CELL_SIZE),
        renderer.texture(make_ground_texture()))
    scenery = renderer.mesh(make_scenery())
    car = renderer.mesh(make_car())

    inputs = InputManager()
    clock = pygame.time.Clock()
    car_pos = np.zeros(3, dtype="f4")
    heading = 0.0
    speed = 0.0
    camera.snap(car_pos, heading)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        state = inputs.poll()

        speed += (state.throttle * ACCELERATION - state.brake * BRAKING) * dt
        if state.throttle == 0.0:
            speed -= DRAG * dt
        speed = min(max(speed, 0.0), MAX_SPEED)
        # Positive steer is right, which is a decreasing heading.
        heading -= state.steer * TURN_RATE * min(1.0, speed / 8.0) * dt
        car_pos += forward(heading) * speed * dt

        camera.follow(car_pos, heading, dt)

        renderer.begin(camera)
        renderer.draw(ground)
        renderer.draw(scenery)
        renderer.draw(car, translate(*car_pos) @ rotate_y(heading))
        renderer.end()
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
