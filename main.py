import sys

import numpy as np
import pygame

from controls.input_state import InputManager
from game import models
from game.car import Car
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
FIELD_OF_VIEW = 65.0
PLAYER_COLOR = (0.9, 0.15, 0.1)


def car_matrix(position, fwd, up):
    return frame_matrix(np.cross(up, fwd), up, fwd, position)


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED

    pygame.init()
    ctx = create_window(WINDOW_SIZE, f"{TITLE} {get_version()}")
    renderer = Renderer(ctx)
    camera = Camera(aspect=WINDOW_SIZE[0] / WINDOW_SIZE[1], fov_y_deg=FIELD_OF_VIEW)

    track = generate(seed)
    checkpoints = [track.length * k / CHECKPOINT_COUNT for k in range(CHECKPOINT_COUNT)]
    track_meshes = track_mesh.build(track, renderer, checkpoints, seed)
    car_mesh = renderer.mesh(models.car(PLAYER_COLOR))

    car = Car(track)
    inputs = InputManager()
    clock = pygame.time.Clock()
    chase_view = False

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_c:
                    chase_view = not chase_view
                    if chase_view:
                        camera.snap(car.pose()[0], car.heading)

        state = inputs.poll()
        car.update(state.steer, state.throttle, state.brake, dt)

        position, fwd, up = car.pose()
        if chase_view:
            camera.follow(position, car.heading, dt)
        else:
            camera.first_person(position, fwd, up)

        renderer.begin(camera)
        for mesh in track_meshes:
            renderer.draw(mesh)
        if chase_view:
            renderer.draw(car_mesh, car_matrix(position, fwd, up))
        renderer.end()
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
