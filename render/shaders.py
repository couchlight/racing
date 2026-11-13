"""GLSL sources."""

# PS1 look:
#   - vertices snapped to the low-res pixel grid (polygon jitter)
#   - affine texture mapping: uv is carried as (uv * w, w) and divided per
#     fragment, which cancels the perspective correction. w is floored at
#     AFFINE_MIN_W so polygons that reach or cross the camera plane fall back
#     to perspective-correct mapping instead of extrapolating to garbage.
#   - per-vertex distance fog
PS1_VERTEX = """
#version 330
uniform mat4 u_mvp;
uniform mat4 u_mv;
uniform vec2 u_resolution;
uniform float u_fog_start;
uniform float u_fog_end;

in vec3 in_pos;
in vec3 in_color;
in vec2 in_uv;

out vec3 v_color;
out vec3 v_uvw;
out float v_fog;

const float AFFINE_MIN_W = 1.0;

void main() {
    vec4 clip = u_mvp * vec4(in_pos, 1.0);
    if (clip.w > 0.0001) {
        vec2 half_res = u_resolution * 0.5;
        vec2 ndc = clip.xy / clip.w;
        ndc = floor(ndc * half_res + 0.5) / half_res;
        clip.xy = ndc * clip.w;
    }
    gl_Position = clip;

    float dist = length((u_mv * vec4(in_pos, 1.0)).xyz);
    v_fog = clamp((dist - u_fog_start) / (u_fog_end - u_fog_start), 0.0, 1.0);
    v_color = in_color;
    float w = max(clip.w, AFFINE_MIN_W);
    v_uvw = vec3(in_uv * w, w);
}
"""

PS1_FRAGMENT = """
#version 330
uniform sampler2D u_texture;
uniform vec3 u_fog_color;

in vec3 v_color;
in vec3 v_uvw;
in float v_fog;

out vec4 f_color;

void main() {
    vec3 color = texture(u_texture, v_uvw.xy / v_uvw.z).rgb * v_color;
    f_color = vec4(mix(color, u_fog_color, v_fog), 1.0);
}
"""

# Fullscreen triangle that upscales the low-res framebuffer to the window.
BLIT_VERTEX = """
#version 330
out vec2 v_uv;
void main() {
    vec2 pos = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    v_uv = pos;
    gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
}
"""

BLIT_FRAGMENT = """
#version 330
uniform sampler2D u_texture;
in vec2 v_uv;
out vec4 f_color;
void main() {
    f_color = texture(u_texture, v_uv);
}
"""
