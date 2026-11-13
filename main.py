import math

import numpy as np
import pygame

from render import primitives
from render.camera import Camera
from render.matrices import rotate_y, translate
from render.renderer import Renderer
from render.window import create_window
from version import get_version

WINDOW_SIZE = (960, 720)
TITLE = "Racing"

# Placeholder test scene — replaced by the procedural track (phase 4) and
# the car model (phase 5).
GROUND_CELLS = 48
GROUND_CELL_SIZE = 5.0
CIRCLE_RADIUS = 24.0
CIRCLE_SPEED = 14.0   # units per second


def make_ground_texture():
    """16x16 noisy asphalt tile with a light edge, so the affine warp is visible."""
    rng = np.random.default_rng(1)
    tile = rng.integers(70, 100, size=(16, 16, 1), dtype="u1").repeat(3, axis=2)
    tile[0, :] = tile[:, 0] = 130
    return tile


def make_scenery():
    """Randomly scattered boxes, kept clear of the driving circle."""
    rng = np.random.default_rng(7)
    boxes = []
    while len(boxes) < 120:
        x, z = rng.uniform(-110.0, 110.0, size=2)
        if abs(math.hypot(x, z) - CIRCLE_RADIUS) < 6.0:
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

    clock = pygame.time.Clock()
    angle = 0.0
    first_frame = True

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # Drive the placeholder car around a circle.
        angle += CIRCLE_SPEED / CIRCLE_RADIUS * dt
        car_pos = np.array([math.sin(angle) * CIRCLE_RADIUS, 0.0,
                            math.cos(angle) * CIRCLE_RADIUS], dtype="f4")
        heading = angle + math.pi / 2.0

        if first_frame:
            camera.snap(car_pos, heading)
            first_frame = False
        else:
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
