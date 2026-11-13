import numpy as np

# Interleaved vertex layout: position (3), colour (3), uv (2)
VERTEX_FORMAT = "3f 3f 2f"
VERTEX_ATTRIBUTES = ("in_pos", "in_color", "in_uv")
VERTEX_SIZE = 8


class Mesh:
    """Triangle list on the GPU. `vertices` is an (N, 8) float array."""

    def __init__(self, ctx, program, vertices, texture=None):
        data = np.ascontiguousarray(vertices, dtype="f4").reshape(-1, VERTEX_SIZE)
        self.vertex_count = len(data)
        self.texture = texture
        self.vbo = ctx.buffer(data.tobytes())
        self.vao = ctx.vertex_array(
            program, [(self.vbo, VERTEX_FORMAT, *VERTEX_ATTRIBUTES)])

    def render(self):
        self.vao.render()
