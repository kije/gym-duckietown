"""
Modern OpenGL shader programs for gym-duckietown.
Replaces legacy fixed-function pipeline with programmable shaders.
"""

from pyglet import gl
from pyglet.graphics.shader import Shader, ShaderProgram
from ctypes import c_float, c_void_p, sizeof, POINTER
import numpy as np


# Basic vertex shader for 3D rendering with color
VERTEX_SHADER = """
#version 330 core

in vec3 position;
in vec3 normal;
in vec2 tex_coords;
in vec4 color;

out vec3 frag_normal;
out vec2 frag_tex_coords;
out vec4 frag_color;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;
uniform mat3 normal_matrix;

void main()
{
    gl_Position = projection * view * model * vec4(position, 1.0);
    frag_normal = normal_matrix * normal;
    frag_tex_coords = tex_coords;
    frag_color = color;
}
"""

# Basic fragment shader for 3D rendering with color and optional texture
FRAGMENT_SHADER = """
#version 330 core

in vec3 frag_normal;
in vec2 frag_tex_coords;
in vec4 frag_color;

out vec4 out_color;

uniform sampler2D tex;
uniform bool use_texture;
uniform vec3 light_dir;

void main()
{
    // Simple diffuse lighting
    vec3 norm = normalize(frag_normal);
    vec3 light = normalize(light_dir);
    float diff = max(dot(norm, light), 0.0);
    float ambient = 0.3;
    float lighting = ambient + (1.0 - ambient) * diff;

    vec4 base_color = frag_color;
    if (use_texture) {
        base_color = texture(tex, frag_tex_coords) * frag_color;
    }

    out_color = vec4(base_color.rgb * lighting, base_color.a);
}
"""

# Simple vertex shader for 2D/unlit rendering
VERTEX_SHADER_SIMPLE = """
#version 330 core

in vec3 position;
in vec4 color;

out vec4 frag_color;

uniform mat4 model;
uniform mat4 view;
uniform mat4 projection;

void main()
{
    gl_Position = projection * view * model * vec4(position, 1.0);
    frag_color = color;
}
"""

# Simple fragment shader for 2D/unlit rendering
FRAGMENT_SHADER_SIMPLE = """
#version 330 core

in vec4 frag_color;
out vec4 out_color;

void main()
{
    out_color = frag_color;
}
"""


class ShaderManager:
    """Manages shader programs for the simulator."""

    def __init__(self):
        self.programs = {}
        self._create_programs()

    def _create_programs(self):
        """Create all shader programs."""
        # Main 3D shader with lighting and textures
        vertex_shader = Shader(VERTEX_SHADER, 'vertex')
        fragment_shader = Shader(FRAGMENT_SHADER, 'fragment')
        self.programs['main'] = ShaderProgram(vertex_shader, fragment_shader)

        # Simple shader for unlit objects (like lines, bounding boxes)
        vertex_shader_simple = Shader(VERTEX_SHADER_SIMPLE, 'vertex')
        fragment_shader_simple = Shader(FRAGMENT_SHADER_SIMPLE, 'fragment')
        self.programs['simple'] = ShaderProgram(vertex_shader_simple, fragment_shader_simple)

    def get_program(self, name='main'):
        """Get a shader program by name."""
        return self.programs.get(name)

    def use_program(self, name='main'):
        """Bind a shader program for use."""
        program = self.programs.get(name)
        if program:
            program.use()
        return program


def set_uniform_matrix4(program, name, matrix):
    """Set a 4x4 matrix uniform in a shader program."""
    if isinstance(matrix, np.ndarray):
        matrix = matrix.flatten().astype('float32')

    # Validate matrix size
    if hasattr(matrix, '__len__') and len(matrix) != 16:
        raise ValueError(f"Matrix uniform '{name}' must have 16 elements, got {len(matrix)}")

    try:
        program[name] = matrix
    except Exception as e:
        raise RuntimeError(f"Failed to set uniform '{name}': {e}")


def set_uniform_matrix3(program, name, matrix):
    """
    Set a 3x3 matrix uniform in a shader program.

    Workaround for Pyglet 2.1.9 bug: Pyglet incorrectly expects mat3 to have
    length 6 instead of 9. We bypass Pyglet's wrapper and call OpenGL directly.
    """
    if isinstance(matrix, np.ndarray):
        matrix = matrix.flatten().astype('float32')

    # Validate matrix size
    if hasattr(matrix, '__len__') and len(matrix) != 9:
        raise ValueError(f"Matrix3 uniform '{name}' must have 9 elements, got {len(matrix)}")

    try:
        # Get the uniform location
        uniform = program._uniforms.get(name)
        if uniform is None:
            raise KeyError(f"Uniform '{name}' not found in shader program")

        # Convert to ctypes array
        from ctypes import c_float
        mat3_array = (c_float * 9)(*matrix)

        # Call OpenGL directly to bypass Pyglet's incorrect length check
        # glUniformMatrix3fv(location, count, transpose, value)
        gl.glUniformMatrix3fv(uniform.location, 1, gl.GL_FALSE, mat3_array)

    except KeyError as e:
        raise RuntimeError(f"Failed to find uniform '{name}': {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to set uniform '{name}': {e}")


def set_uniform_vector3(program, name, vector):
    """Set a vec3 uniform in a shader program."""
    if isinstance(vector, (list, tuple, np.ndarray)):
        if len(vector) < 3:
            raise ValueError(f"Vector3 uniform '{name}' needs at least 3 components, got {len(vector)}")
        program[name] = tuple(vector[:3])
    else:
        program[name] = vector


def set_uniform_bool(program, name, value):
    """Set a boolean uniform in a shader program."""
    try:
        program[name] = bool(value)
    except Exception as e:
        raise RuntimeError(f"Failed to set uniform '{name}': {e}")


def set_uniform_float(program, name, value):
    """Set a float uniform in a shader program."""
    try:
        program[name] = float(value)
    except Exception as e:
        raise RuntimeError(f"Failed to set uniform '{name}': {e}")
