"""
Modern matrix stack implementation to replace legacy OpenGL matrix operations.
Replaces glPushMatrix/glPopMatrix, glTranslatef, glScalef, glRotatef.
"""

import numpy as np
from pyglet.math import Mat4, Vec3
from typing import List


class MatrixStack:
    """
    A matrix stack that replicates the behavior of legacy OpenGL matrix operations.
    Uses pyglet.math.Mat4 for efficient matrix operations.
    """

    def __init__(self):
        self.stack: List[Mat4] = [Mat4()]  # Start with identity matrix

    def push(self):
        """Push the current matrix onto the stack (like glPushMatrix)."""
        # Create a true copy using tuple unpacking (Mat4 is a NamedTuple with 16 fields)
        current = self.stack[-1]
        self.stack.append(Mat4(*current))

    def pop(self):
        """Pop the top matrix from the stack (like glPopMatrix)."""
        if len(self.stack) > 1:
            self.stack.pop()
        else:
            raise RuntimeError("Matrix stack underflow")

    def load_identity(self):
        """Load the identity matrix as the current matrix."""
        self.stack[-1] = Mat4()

    def translate(self, x, y, z):
        """Apply translation to the current matrix (like glTranslatef)."""
        translation = Mat4.from_translation(Vec3(x, y, z))
        self.stack[-1] = self.stack[-1] @ translation

    def scale(self, x, y, z):
        """Apply scaling to the current matrix (like glScalef)."""
        scaling = Mat4.from_scale(Vec3(x, y, z))
        self.stack[-1] = self.stack[-1] @ scaling

    def rotate(self, angle_deg, x, y, z):
        """
        Apply rotation to the current matrix (like glRotatef).

        Args:
            angle_deg: Rotation angle in degrees
            x, y, z: Rotation axis components
        """
        # Normalize the rotation axis
        axis = Vec3(x, y, z)
        length = (x*x + y*y + z*z) ** 0.5
        if length > 0:
            axis = Vec3(x/length, y/length, z/length)

        # Convert degrees to radians
        angle_rad = np.radians(angle_deg)

        rotation = Mat4.from_rotation(angle_rad, axis)
        self.stack[-1] = self.stack[-1] @ rotation

    def get_matrix(self) -> Mat4:
        """Get the current top matrix."""
        return self.stack[-1]

    def get_matrix_array(self) -> np.ndarray:
        """Get the current matrix as a numpy array suitable for shader uniforms."""
        # Pyglet Mat4 stores in column-major order, which is what OpenGL expects
        matrix = self.stack[-1]
        if not isinstance(matrix, Mat4):
            raise TypeError(f"Matrix stack contains non-Mat4 object: {type(matrix)}")

        # Convert Mat4 to tuple, then to numpy array
        # The explicit tuple conversion ensures we get a flat sequence of 16 elements
        mat_tuple = tuple(matrix)

        # Handle potential numpy scalar contamination by converting to float32 explicitly
        # This can happen when numpy operations are used to compute matrix values
        return np.array([float(x) for x in mat_tuple], dtype=np.float32)


class ModelViewProjection:
    """
    Manages the model, view, and projection matrix stacks.
    Replaces the legacy GL_MODELVIEW and GL_PROJECTION matrices.
    """

    def __init__(self):
        self.model = MatrixStack()
        self.view = MatrixStack()
        self.projection = MatrixStack()

    def reset(self):
        """Reset all matrices to identity."""
        self.model = MatrixStack()
        self.view = MatrixStack()
        self.projection = MatrixStack()


# Global matrix stack instance
_mvp = None


def get_mvp() -> ModelViewProjection:
    """Get the global ModelViewProjection instance."""
    global _mvp
    if _mvp is None:
        _mvp = ModelViewProjection()
    return _mvp


def reset_mvp():
    """Reset the global ModelViewProjection instance."""
    global _mvp
    _mvp = ModelViewProjection()
