# coding=utf-8
import math
from typing import Dict, Tuple

import numpy as np
from pyglet import gl
#from pyglet.gl import gluNewQuadric, gluSphere
import pyglet.graphics

from duckietown_world import MapFormat1Constants
from duckietown_world.resources import get_resource_path
from .collision import (
    agent_boundbox,
    calculate_safety_radius,
    generate_corners,
    generate_norm,
    heading_vec,
    intersects_single_obj,
)
from .graphics import load_texture, rotate_point
from .objmesh import ObjMesh
from .shaders import set_uniform_matrix4, set_uniform_vector3, set_uniform_bool
from .matrix_stack import get_mvp


def create_sphere(radius, sectors, stacks):
    """
    Generate vertices and indices for a sphere.

    Args:
        radius: sphere radius
        sectors: number of longitude divisions
        stacks: number of latitude divisions

    Returns:
        vertices, normals, indices for the sphere
    """
    vertices = []
    normals = []
    texcoords = []

    sector_step = 2 * math.pi / sectors
    stack_step = math.pi / stacks

    # Generate vertices
    for i in range(stacks + 1):
        stack_angle = math.pi / 2 - i * stack_step  # from pi/2 to -pi/2
        xy = radius * math.cos(stack_angle)  # radius at current stack
        z = radius * math.sin(stack_angle)

        for j in range(sectors + 1):
            sector_angle = j * sector_step  # from 0 to 2pi

            # Vertex position
            x = xy * math.cos(sector_angle)
            y = xy * math.sin(sector_angle)
            vertices.extend([x, y, z])

            # Normalized normal (for unit sphere, normal = position)
            nx = x / radius
            ny = y / radius
            nz = z / radius
            normals.extend([nx, ny, nz])

            # Texture coordinates
            s = j / sectors
            t = i / stacks
            texcoords.extend([s, t])

    # Add white color for all vertices
    colors = [1.0, 1.0, 1.0, 1.0] * ((stacks + 1) * (sectors + 1))  # RGBA white

    # Generate indices for triangles
    indices = []
    for i in range(stacks):
        k1 = i * (sectors + 1)
        k2 = k1 + sectors + 1

        for j in range(sectors):
            if i != 0:
                indices.extend([k1, k2, k1 + 1])
            if i != (stacks - 1):
                indices.extend([k1 + 1, k2, k2 + 1])

            k1 += 1
            k2 += 1

    return vertices, normals, texcoords, indices, colors


class SphereCache:
    """Cache for sphere meshes to avoid regenerating geometry every frame."""

    def __init__(self):
        self.spheres = {}  # key: (shader_id, radius, sectors, stacks) -> vertex_list
        self.geometry_cache = {}  # key: (radius, sectors, stacks) -> (vertices, normals, texcoords, indices)

    def get_sphere(self, shader_program, radius, sectors=20, stacks=20):
        """
        Get or create a sphere vertex list for the given shader program.

        Args:
            shader_program: The ShaderProgram to create the vertex list with
            radius: Sphere radius
            sectors: Number of longitude divisions
            stacks: Number of latitude divisions

        Returns:
            VertexList for the sphere
        """
        if shader_program is None:
            return None

        # Use shader program ID for cache key (different shaders may have different attributes)
        shader_id = id(shader_program)
        cache_key = (shader_id, radius, sectors, stacks)

        if cache_key not in self.spheres:
            # Check if we have the geometry cached
            geom_key = (radius, sectors, stacks)
            if geom_key not in self.geometry_cache:
                self.geometry_cache[geom_key] = create_sphere(radius, sectors, stacks)

            vertices, normals, texcoords, indices, colors = self.geometry_cache[geom_key]

            # Create vertex list using Pyglet 2.0+ API
            # Note: attribute names must match shader variable names exactly
            vertex_list = shader_program.vertex_list_indexed(
                len(vertices) // 3,
                gl.GL_TRIANGLES,
                indices,
                position=('f', vertices),
                normal=('f', normals),  # 'normal' not 'normals'
                tex_coords=('f', texcoords),
                color=('f', colors)  # 'color' not 'colors'
            )
            self.spheres[cache_key] = vertex_list

        return self.spheres[cache_key]


# Global sphere cache
_sphere_cache = SphereCache()


def draw_sphere(radius, sectors=20, stacks=20, shader_program=None):
    """
    Draw a sphere using modern OpenGL vertex arrays.

    Args:
        radius: Sphere radius
        sectors: Number of longitude divisions
        stacks: Number of latitude divisions
        shader_program: ShaderProgram to use for rendering
    """
    if shader_program is None:
        return  # Can't draw without a shader in modern OpenGL

    vertex_list = _sphere_cache.get_sphere(shader_program, radius, sectors, stacks)
    if vertex_list:
        vertex_list.draw(gl.GL_TRIANGLES)

class WorldObj:
    visible: bool
    color: Tuple[float, float, float, float]
    safety_radius_mult: float

    obj_corners: np.array
    obj_norm: np.array
    mesh: ObjMesh
    kind: MapFormat1Constants.ObjectKind

    def __init__(self, obj, domain_rand: bool, safety_radius_mult: float):
        """
        Initializes the object and its properties
        """
        # XXX this is relied on by things but it is not always set
        # (Static analysis complains)
        self.visible = True
        # same
        self.color = (0, 0, 0, 1)
        # maybe have an abstract method is_visible, get_color()

        self.kind = obj["kind"]
        self.mesh = obj["mesh"]
        self.pos = obj["pos"]
        self.scale = obj["scale"]
        # self.y_rot =
        self.optional = obj["optional"]
        self.min_coords = obj["mesh"].min_coords
        self.max_coords = obj["mesh"].max_coords
        self.static = obj["static"]
        self.safety_radius = safety_radius_mult * calculate_safety_radius(self.mesh, self.scale)

        self.domain_rand = domain_rand
        self.angle = obj["angle"]
        self.y_rot = np.rad2deg(self.angle)

        #  Find corners and normal vectors assoc w. object
        self.obj_corners = generate_corners(
            self.pos, self.min_coords, self.max_coords, self.angle, self.scale
        )
        self.obj_norm = generate_norm(self.obj_corners)

        self.x_rot = 0  # Niki-added
        self.z_rot = 0  # Niki-added

    def render_mesh(self, segment: bool, enable_leds: bool, shader_program=None):
        self.mesh.render(segment=segment, shader_program=shader_program)
        if enable_leds and self.kind == MapFormat1Constants.KIND_DUCKIEBOT:
            mvp = get_mvp()
            s_main = 0.01  # 1 cm sphere
            s_halo = 0.04
            height = 0.05
            positions = {
                "front_left": [0.1, -0.05, height],
                "front_right": [0.1, +0.05, height],
                "center": [0.1, +0.0, height],
                "back_left": [-0.1, -0.05, height],
                "back_right": [-0.1, +0.05, height],
            }
            if isinstance(self, DuckiebotObj):
                colors = self.leds_color
            else:
                colors = {
                    "center": (0, 0, 1),
                    "front_left": (0, 0, 1),
                    "front_right": (0, 0, 1),
                    "back_left": (0, 0, 1),
                    "back_right": (0, 0, 1),
                }

            # Enable blending for LED halos (still valid in modern OpenGL)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE)

            for light_name, (px, py, pz) in positions.items():
                color = np.clip(colors[light_name], 0, +1)
                color_intensity = float(np.mean(color))

                # Apply LED position transformation
                mvp.model.push()
                mvp.model.translate(px, pz, py)

                # Update shader with current transformation
                if shader_program:
                    set_uniform_matrix4(shader_program, 'model', mvp.model.get_matrix_array())
                    # Note: Sphere color handled by shader lighting, not glColor4f

                # Draw main LED (full opacity)
                draw_sphere(s_main, 10, 10, shader_program=shader_program)

                # Draw halo (translucent)
                s_halo_effective = color_intensity * s_halo
                draw_sphere(s_halo_effective, 10, 10, shader_program=shader_program)

                mvp.model.pop()

            # Restore blend mode
            gl.glBlendFunc(gl.GL_ONE, gl.GL_ZERO)
            gl.glDisable(gl.GL_BLEND)

    def render(self, draw_bbox: bool, enable_leds: bool, segment: bool = False, shader_program=None):
        """
        Renders the object to screen
        """
        if not self.visible:
            return

        mvp = get_mvp()

        # Draw the bounding box
        if draw_bbox:
            # Create vertices for the 4 corners at y=0.01
            vertices = []
            for i in range(4):
                vertices.extend([
                    self.obj_corners.T[0, i],
                    0.01,
                    self.obj_corners.T[1, i]
                ])

            # Red color for all vertices (RGBA format, normalized bytes)
            colors = [255, 0, 0, 255] * 4  # RGBA red for 4 vertices

            # Use simple shader for unlit rendering if available
            if shader_program:
                shader_program.use()
                set_uniform_matrix4(shader_program, 'model', mvp.model.get_matrix_array())
                set_uniform_matrix4(shader_program, 'view', mvp.view.get_matrix_array())
                set_uniform_matrix4(shader_program, 'projection', mvp.projection.get_matrix_array())

                # Create and draw vertex list using Pyglet 2.0+ API
                bbox_vlist = shader_program.vertex_list(
                    4,
                    gl.GL_LINE_LOOP,
                    position=('f', vertices),
                    color=('Bn', colors)  # 'color' not 'colors'
                )
                bbox_vlist.draw(gl.GL_LINE_LOOP)
            else:
                # Fallback if no shader program available (should not happen in modern pipeline)
                pass

        # Apply object transformations using matrix stack
        mvp.model.push()
        mvp.model.translate(*self.pos)
        mvp.model.scale(self.scale, self.scale, self.scale)
        mvp.model.rotate(self.x_rot, 1, 0, 0)
        mvp.model.rotate(self.y_rot, 0, 1, 0)
        mvp.model.rotate(self.z_rot, 0, 0, 1)

        # Render the mesh (color will be handled by shader)
        self.render_mesh(segment, enable_leds=enable_leds, shader_program=shader_program)

        mvp.model.pop()

    # Below are the functions that need to
    # be reimplemented for any dynamic object
    def check_collision(self, agent_corners, agent_norm):
        """
        See if the agent collided with this object
        For static, return false (static collisions checked w
        numpy in a batch operation)
        """
        if not self.static:
            raise NotImplementedError
        return False

    def proximity(self, agent_pos, agent_safety_rad):
        """
        See if the agent is too close to this object
        For static, return 0 (static safedriving checked w
        numpy in a batch operation)
        """
        if not self.static:
            raise NotImplementedError
        return 0.0

    def step(self, delta_time):
        """
        Use a motion model to move the object in the world
        """
        if not self.static:
            raise NotImplementedError


class DuckiebotObj(WorldObj):
    leds_color: Dict[str, Tuple[float, float, float]]

    def __init__(
        self,
        obj,
        domain_rand,
        safety_radius_mult,
        wheel_dist,
        robot_width,
        robot_length,
        gain=2.0,
        trim=0.0,
        radius=0.0318,
        k=27.0,
        limit=1.0,
    ):
        WorldObj.__init__(self, obj, domain_rand, safety_radius_mult)
        if self.domain_rand:
            self.follow_dist = np.random.uniform(0.3, 0.4)
            self.velocity = np.random.uniform(0.05, 0.15)
            self.gain = gain + np.random.uniform(-0.3, 0.3)
            self.trim = trim + np.random.uniform(-0.1, 0.1) + 2
            self.radius = radius + 0.0002 * np.random.uniform(-1, 1)
            self.wheel_dist = wheel_dist + 0.01 * np.random.uniform(-1, 1)
            self.robot_width = robot_width + 0.01 * np.random.uniform(-1, 1)
            self.robot_length = robot_length + 0.01 * np.random.uniform(-1, 1)
        else:
            self.follow_dist = 0.3
            self.velocity = 0.1
            self.gain = gain
            self.trim = trim
            self.radius = radius
            self.wheel_dist = wheel_dist
            self.robot_width = robot_width
            self.robot_length = robot_length

        self.max_iterations = 1000
        self.leds_color = {
            "center": (0.0, 0.0, 0.2),
            "front_left": (0.5, 0.5, 0.5),
            "front_right": (0.5, 0.5, 0.5),
            "back_left": (0.5, 0.0, 0.0),
            "back_right": (0.5, 0.0, 0.0),
        }
        # TODO: Make these DR as well
        self.k = k
        self.limit = limit

    # FIXME: this does not follow the same signature as WorldOb
    def step_duckiebot(self, delta_time, closest_curve_point, objects):
        """
        Take a step, implemented as a PID controller
        """

        # Find the curve point closest to the agent, and the tangent at that point
        closest_point, closest_tangent = closest_curve_point(self.pos, self.angle)
        if closest_point is None or closest_tangent is None:
            msg = f"Cannot find closest point/tangent from {self.pos}, {self.angle} "
            raise Exception(msg)

        iterations = 0
        lookup_distance = self.follow_dist
        curve_point = None
        while iterations < self.max_iterations:
            # Project a point ahead along the curve tangent,
            # then find the closest point to to that
            follow_point = closest_point + closest_tangent * lookup_distance
            curve_point, _ = closest_curve_point(follow_point, self.angle)

            # If we have a valid point on the curve, stop
            if curve_point is not None:
                break

            iterations += 1
            lookup_distance *= 0.5

        # Compute a normalized vector to the curve point
        point_vec = curve_point - self.pos
        point_vec /= np.linalg.norm(point_vec)

        dot = np.dot(get_right_vec(self.angle), point_vec)
        steering = self.gain * -dot

        self._update_pos([self.velocity, steering], delta_time)

    def check_collision(self, agent_corners, agent_norm):
        """
        See if the agent collided with this object
        """
        return intersects_single_obj(agent_corners, self.obj_corners.T, agent_norm, self.obj_norm)

    def proximity(self, agent_pos, agent_safety_rad):
        """
        See if the agent is too close to this object
        based on a heuristic for the "overlap" between
        their safety circles
        """
        d = np.linalg.norm(agent_pos - self.pos)
        score = d - agent_safety_rad - self.safety_radius

        return min(0, score)

    def _update_pos(self, action, deltaTime):
        vel, angle = action

        # assuming same motor constants k for both motors
        k_r = self.k
        k_l = self.k

        # adjusting k by gain and trim
        k_r_inv = (self.gain + self.trim) / k_r
        k_l_inv = (self.gain - self.trim) / k_l

        omega_r = (vel + 0.5 * angle * self.wheel_dist) / self.radius
        omega_l = (vel - 0.5 * angle * self.wheel_dist) / self.radius

        # conversion from motor rotation rate to duty cycle
        u_r = omega_r * k_r_inv
        u_l = omega_l * k_l_inv

        # limiting output to limit, which is 1.0 for the duckiebot
        u_r_limited = max(min(u_r, self.limit), -self.limit)
        u_l_limited = max(min(u_l, self.limit), -self.limit)

        # If the wheel velocities are the same, then there is no rotation
        if u_l_limited == u_r_limited:
            self.pos = self.pos + deltaTime * u_l_limited * get_dir_vec(self.angle)
            return

        # Compute the angular rotation velocity about the ICC (center of curvature)
        w = (u_r_limited - u_l_limited) / self.wheel_dist

        # Compute the distance to the center of curvature
        r = (self.wheel_dist * (u_l_limited + u_r_limited)) / (2 * (u_l_limited - u_r_limited))

        # Compute the rotation angle for this time step
        rotAngle = w * deltaTime

        # Rotate the robot's position around the center of rotation
        r_vec = get_right_vec(self.angle)
        px, py, pz = self.pos
        cx = px + r * r_vec[0]
        cz = pz + r * r_vec[2]
        npx, npz = rotate_point(px, pz, cx, cz, rotAngle)

        # Update position
        self.pos = np.array([npx, py, npz])

        # Update the robot's direction angle
        self.angle += rotAngle
        self.y_rot += rotAngle * 180 / np.pi

        # Recompute the bounding boxes (BB) for the duckiebot
        self.obj_corners = agent_boundbox(
            self.pos, self.robot_width, self.robot_length, get_dir_vec(self.angle), get_right_vec(self.angle)
        )


class DuckieObj(WorldObj):
    def __init__(self, obj, domain_rand: bool, safety_radius_mult: float, walk_distance: float):
        WorldObj.__init__(self, obj, domain_rand, safety_radius_mult)

        self.walk_distance = walk_distance

        # Dynamic duckie stuff

        # Randomize velocity and wait time
        if self.domain_rand:
            self.pedestrian_wait_time = np.random.randint(3, 20)
            self.vel = np.abs(np.random.normal(0.02, 0.005))
        else:
            self.pedestrian_wait_time = 8
            self.vel = 0.02

        # Movement parameters
        self.heading = heading_vec(self.angle)
        self.start = np.copy(self.pos)
        self.center = self.pos
        self.pedestrian_active = False

        # Walk wiggle parameter
        self.wiggle = np.random.choice([14, 15, 16], 1)
        self.wiggle = np.pi / self.wiggle

        self.time = 0

    def check_collision(self, agent_corners, agent_norm):
        """
        See if the agent collided with this object
        """
        return intersects_single_obj(agent_corners, self.obj_corners.T, agent_norm, self.obj_norm)

    def proximity(self, agent_pos, agent_safety_rad):
        """
        See if the agent is too close to this object
        based on a heuristic for the "overlap" between
        their safety circles
        """
        d = np.linalg.norm(agent_pos - self.center)
        score = d - agent_safety_rad - self.safety_radius

        return min(0, score)

    def step(self, delta_time: float):
        """
        Use a motion model to move the object in the world
        """

        self.time += delta_time

        # If not walking, no need to do anything
        if not self.pedestrian_active:
            self.pedestrian_wait_time -= delta_time
            if self.pedestrian_wait_time <= 0:
                self.pedestrian_active = True
            return

        # Update centers and bounding box
        vel_adjust = self.heading * self.vel
        self.center += vel_adjust
        self.obj_corners += vel_adjust[[0, -1]]

        distance = np.linalg.norm(self.center - self.start)

        if distance > self.walk_distance:
            self.finish_walk()

        self.pos = self.center
        angle_delta = self.wiggle * math.sin(48 * self.time)
        self.y_rot = (self.angle + angle_delta) * (180 / np.pi)
        self.obj_norm = generate_norm(self.obj_corners)
        # print("now at pos", self.pos)

    def finish_walk(self):
        """
        After duckie crosses, update relevant attributes
        (vel, rot, wait time until next walk)
        """
        self.start = np.copy(self.center)
        self.angle += np.pi
        self.pedestrian_active = False

        if self.domain_rand:
            # Assign a random velocity (in opp. direction) and a wait time
            # TODO: Fix this: This will go to 0 over time
            self.vel = -1 * np.sign(self.vel) * np.abs(np.random.normal(0.02, 0.005))
            self.pedestrian_wait_time = np.random.randint(3, 20)
        else:
            # Just give it the negative of its current velocity
            self.vel *= -1
            self.pedestrian_wait_time = 8


class TrafficLightObj(WorldObj):
    def __init__(self, obj, domain_rand, safety_radius_mult):
        WorldObj.__init__(self, obj, domain_rand, safety_radius_mult)

        self.texs = [
            load_texture(get_resource_path("trafficlight_card0.jpg")),
            load_texture(get_resource_path("trafficlight_card1.jpg")),
        ]
        self.time = 0

        # Frequency and current pattern of the lights
        if self.domain_rand:
            self.freq = np.random.randint(4, 7)
            self.pattern = np.random.randint(0, 2)
        else:
            self.freq = 5
            self.pattern = 0

        # Use the selected pattern
        self.mesh.textures[0] = self.texs[self.pattern]

    def step(self, delta_time: float) -> None:
        """
        Changes the light color periodically
        """

        self.time += delta_time
        if round(self.time, 3) % self.freq == 0:  # Swap patterns
            self.pattern ^= 1
            self.mesh.textures[0] = self.texs[self.pattern]

    def is_green(self, direction="N"):
        if direction == "N" or direction == "S":
            if self.y_rot == 45 or self.y_rot == 135:
                return self.pattern == 0
            elif self.y_rot == 225 or self.y_rot == 315:
                return self.pattern == 1
        elif direction == "E" or direction == "W":
            if self.y_rot == 45 or self.y_rot == 135:
                return self.pattern == 1
            elif self.y_rot == 225 or self.y_rot == 315:
                return self.pattern == 0
        return False


class CheckerboardObj(WorldObj):
    # Copied from the duckie class above
    def __init__(self, obj, domain_rand, safety_radius_mult, walk_distance):
        WorldObj.__init__(self, obj, domain_rand, safety_radius_mult)

        self.walk_distance = walk_distance + 0.25

        # Dynamic checkerboard
        self.pedestrian_wait_time = 0
        self.vel = 0.01

        # Randomize velocity and wait time
        # if self.domain_rand:
        #     self.pedestrian_wait_time = np.random.randint(3, 20)
        #     self.vel = np.abs(np.random.normal(0.02, 0.005))
        # else:
        #     self.pedestrian_wait_time = 8
        #     self.vel = 0.02

        # # Movement parameters
        self.heading = heading_vec(self.angle)
        self.start = np.copy(self.pos)
        self.reset_start = np.copy(self.pos)
        self.center = self.pos
        self.pedestrian_active = False

        # # Walk wiggle parameter
        self.wiggle = np.random.choice([14, 15, 16], 1)
        self.wiggle = np.pi / self.wiggle

        self.time = 0
        # increase this paramter to delay the intrinsic calibration
        self.steps = -20

    def check_collision(self, agent_corners, agent_norm):
        """
        See if the agent collided with this object
        """
        return intersects_single_obj(agent_corners, self.obj_corners.T, agent_norm, self.obj_norm)

    def proximity(self, agent_pos, agent_safety_rad):
        """
        See if the agent is too close to this object
        based on a heuristic for the "overlap" between
        their safety circles
        """
        d = np.linalg.norm(agent_pos - self.center)
        score = d - agent_safety_rad - self.safety_radius

        return min(0, score)

    def step(self, delta_time):
        """
        Use a motion model to move the object in the world
        """

        self.time += delta_time
        step = self.steps  # %max_steps if self.steps>=0 else self.steps
        offset = 20
        scaled_offset = offset * 1.0 / 3000
        move = True
        # move the checkerboard back and foreward
        if step < 0:
            pass
        elif step < 40:
            self.center += np.array([scaled_offset, 0, 0])
        elif step < 135:
            self.center -= np.array([scaled_offset, 0, 0])
        elif step < 170:
            self.center += np.array([scaled_offset, 0, 0])

        # Move left and right
        elif step < 200:
            self.center += np.array([0, 0, scaled_offset])
        elif step < 260:
            self.center -= np.array([0, 0, scaled_offset])
        elif step < 290:
            self.center += np.array([0, 0, scaled_offset])

        # Move up and down
        elif step < 310:
            self.center += np.array([0, scaled_offset, 0])
        elif step < 330:
            self.center -= np.array([0, scaled_offset, 0])

        # move forward
        elif step < 355:
            self.center -= np.array([scaled_offset, 0, 0])

        # repeat move up and down
        elif step < 370:
            self.center -= np.array([0, scaled_offset, 0])
        elif step < 385:
            self.center += np.array([0, scaled_offset, 0])

        # move backward
        elif step < 420:
            self.center += np.array([scaled_offset, 0, 0])

        # reset to initial position
        else:
            self.center = np.copy(self.reset_start)
            self.steps = -20
            move = False
        if move:
            self.steps += 2
        self.pos = self.center

    def finish_walk(self):
        """
        After duckie crosses, update relevant attributes
        (vel, rot, wait time until next walk)
        """
        self.start = np.copy(self.center)
        self.angle += np.pi
        self.pedestrian_active = False

        if self.domain_rand:
            # Assign a random velocity (in opp. direction) and a wait time
            # TODO: Fix this: This will go to 0 over time
            self.vel = -1 * np.sign(self.vel) * np.abs(np.random.normal(0.02, 0.005))
            self.pedestrian_wait_time = np.random.randint(3, 20)
        else:
            # Just give it the negative of its current velocity
            self.vel *= -1
            self.pedestrian_wait_time = 8


def get_dir_vec(angle: float) -> np.ndarray:
    x = math.cos(angle)
    z = -math.sin(angle)
    return np.array([x, 0, z])


def get_right_vec(angle: float) -> np.ndarray:
    x = math.sin(angle)
    z = math.cos(angle)
    return np.array([x, 0, z])
