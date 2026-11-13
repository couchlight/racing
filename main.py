import sys

import numpy as np
import pygame

from controls.input_state import InputManager
from render import primitives
from render.camera import Camera
from render.matrices import frame_matrix
from render.renderer import Renderer
from render.window import create_window
from track import mesh as track_mesh
from track.generator import generate
from version import get_version

WINDOW_SIZE = (960, 720)
TITLE = "Racing"
DEFAULT_SEED = 1
CHECKPOINT_COUNT = 4

# Placeholder driving model, in track space — replaced by the car (phase 5).
MAX_SPEED = 60.0      # metres per second
ACCELERATION = 18.0
BRAKING = 35.0
DRAG = 4.0            # deceleration when coasting
SLIDE_RATE = 8.0      # lateral metres per second at full steer


def make_car():
    body = primitives.box((1.7, 0.6, 3.6), (0.9, 0.15, 0.1), base_y=0.25)
    cabin = primitives.translated(
        primitives.box((1.4, 0.5, 1.6), (0.15, 0.2, 0.3), base_y=0.85),
        (0.0, 0.0, -0.3))
    return np.concatenate([body, cabin])


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED

    pygame.init()
    ctx = create_window(WINDOW_SIZE, f"{TITLE} {get_version()}")
    renderer = Renderer(ctx)
    camera = Camera(aspect=WINDOW_SIZE[0] / WINDOW_SIZE[1])

    track = generate(seed)
    checkpoints = [track.length * k / CHECKPOINT_COUNT for k in range(CHECKPOINT_COUNT)]
    track_meshes = track_mesh.build(track, renderer, checkpoints, seed)
    car = renderer.mesh(make_car())

    inputs = InputManager()
    clock = pygame.time.Clock()
    distance = 0.0
    lateral = 0.0
    speed = 0.0
    lateral_limit = track.half_width - 1.0
    camera.snap(track.surface(distance, lateral).astype("f4"), track.heading(distance))

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)

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
        distance += speed * dt
        lateral += state.steer * SLIDE_RATE * min(1.0, speed / 8.0) * dt
        lateral = min(max(lateral, -lateral_limit), lateral_limit)

        car_pos = track.surface(distance, lateral).astype("f4")
        tangent, banked_right, normal = track.orientation(distance)
        camera.follow(car_pos, track.heading(distance), dt)

        renderer.begin(camera)
        for mesh in track_meshes:
            renderer.draw(mesh)
        renderer.draw(car, frame_matrix(-banked_right, normal, tangent, car_pos))
        renderer.end()
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
