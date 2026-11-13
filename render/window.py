import moderngl
import pygame


def create_window(size, title):
    """Open a pygame OpenGL window and return its ModernGL context."""
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
    pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
    pygame.display.gl_set_attribute(
        pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
    pygame.display.set_mode(size, pygame.OPENGL | pygame.DOUBLEBUF)
    pygame.display.set_caption(title)
    ctx = moderngl.create_context()
    print(f"GL: {ctx.info['GL_RENDERER']} / {ctx.info['GL_VERSION']}")
    return ctx
