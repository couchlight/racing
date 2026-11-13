import moderngl
import numpy as np

from render import shaders
from render.mesh import Mesh

INTERNAL_SIZE = (320, 240)


class Renderer:
    """Draws meshes into a low-res framebuffer, then upscales it to the window
    with nearest-neighbour filtering."""

    def __init__(self, ctx, internal_size=INTERNAL_SIZE):
        self.ctx = ctx
        self.internal_size = internal_size
        self.fog_color = (0.55, 0.65, 0.8)
        self.fog_start = 60.0
        self.fog_end = 230.0

        self.program = ctx.program(vertex_shader=shaders.PS1_VERTEX,
                                   fragment_shader=shaders.PS1_FRAGMENT)
        self.program["u_resolution"].value = internal_size
        self.program["u_texture"].value = 0

        self.color = ctx.texture(internal_size, 3)
        self.color.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.fbo = ctx.framebuffer(
            [self.color], ctx.depth_renderbuffer(internal_size))

        self.blit_program = ctx.program(vertex_shader=shaders.BLIT_VERTEX,
                                        fragment_shader=shaders.BLIT_FRAGMENT)
        self.blit_program["u_texture"].value = 0
        self.blit_vao = ctx.vertex_array(self.blit_program, [])

        self.overlay_texture = ctx.texture(internal_size, 4)
        self.overlay_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # Bound for meshes that have no texture.
        self.white = self.texture(np.full((1, 1, 3), 255, dtype="u1"))

        self._view = None
        self._projection = None

    def texture(self, pixels):
        """Create a nearest-filtered, repeating texture from an (H, W, 3) uint8 array."""
        height, width = pixels.shape[:2]
        tex = self.ctx.texture((width, height), 3, pixels.tobytes())
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        return tex

    def mesh(self, vertices, texture=None):
        return Mesh(self.ctx, self.program, vertices, texture)

    def begin(self, camera):
        self._view = camera.view()
        self._projection = camera.projection
        self.fbo.use()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.clear(*self.fog_color)
        self.program["u_fog_color"].value = self.fog_color
        self.program["u_fog_start"].value = self.fog_start
        self.program["u_fog_end"].value = self.fog_end

    def draw(self, mesh, model=None):
        mv = self._view if model is None else self._view @ model
        mvp = self._projection @ mv
        # numpy is row-major, GL expects column-major.
        self.program["u_mv"].write(mv.T.astype("f4").tobytes())
        self.program["u_mvp"].write(mvp.T.astype("f4").tobytes())
        (mesh.texture or self.white).use(0)
        mesh.render()

    def overlay(self, pixels):
        """Alpha-blend an RGBA image over the low-res frame. `pixels` is
        internal_size RGBA bytes, bottom row first. Call between begin() and end()."""
        self.overlay_texture.write(pixels)
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.overlay_texture.use(0)
        self.blit_vao.render(moderngl.TRIANGLES, vertices=3)
        self.ctx.disable(moderngl.BLEND)

    def end(self):
        self.ctx.screen.use()
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.color.use(0)
        self.blit_vao.render(moderngl.TRIANGLES, vertices=3)
