import struct

import pygame

from render.window import create_window
from version import get_version

WINDOW_SIZE = (960, 720)
TITLE = "Racing"

VERTEX_SHADER = """
#version 330
in vec2 in_pos;
in vec3 in_color;
out vec3 v_color;
void main() {
    v_color = in_color;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330
in vec3 v_color;
out vec4 f_color;
void main() {
    f_color = vec4(v_color, 1.0);
}
"""


class Triangle:
    """Phase 0 smoke test — replaced by the renderer in phase 1."""

    def __init__(self, ctx):
        prog = ctx.program(vertex_shader=VERTEX_SHADER,
                           fragment_shader=FRAGMENT_SHADER)
        vertices = struct.pack(
            "15f",
            -0.6, -0.5, 1.0, 0.0, 0.0,
            0.6, -0.5, 0.0, 1.0, 0.0,
            0.0, 0.6, 0.0, 0.0, 1.0,
        )
        vbo = ctx.buffer(vertices)
        self.vao = ctx.vertex_array(prog, [(vbo, "2f 3f", "in_pos", "in_color")])

    def draw(self):
        self.vao.render()


def main():
    pygame.init()
    ctx = create_window(WINDOW_SIZE, f"{TITLE} {get_version()}")
    triangle = Triangle(ctx)
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        ctx.clear(0.05, 0.05, 0.1)
        triangle.draw()
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
