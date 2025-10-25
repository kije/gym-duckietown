"""
MapBuilder: Fluent API for programmatic map construction.

This module provides a builder pattern for creating Duckietown maps programmatically
instead of manually writing YAML files. Supports type safety, validation, and YAML export.

Example:
    >>> from gym_duckietown import MapBuilder
    >>>
    >>> # Create a simple loop map
    >>> map_data = (MapBuilder(tile_size=0.585)
    ...     .add_tile(0, 0, 'straight', orientation='N')
    ...     .add_tile(1, 0, 'curve_left', orientation='N')
    ...     .add_tile(1, 1, 'straight', orientation='W')
    ...     .add_object('duckie1', kind='duckie', pos=[1.5, 2.0], rotate=45)
    ...     .set_start_tile([0, 0])
    ...     .build())
    >>>
    >>> # Use with DuckietownEnv
    >>> from gym_duckietown.envs import DuckietownEnv
    >>> env = DuckietownEnv(map_data=map_data)

    >>> # Use template for common patterns
    >>> map_data = MapBuilder.create_loop(size=4).build()

    >>> # Export to YAML
    >>> builder = MapBuilder.create_loop(size=4)
    >>> builder.add_object('cone1', 'cone', pos=[2.0, 2.0])
    >>> map_data = builder.build()
    >>> MapBuilder.save_yaml(map_data, 'my_generated_map.yaml')
"""

import copy
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml


class MapBuilder:
    """
    Fluent API for programmatic map construction.

    Provides a chainable interface for building Duckietown maps with full type safety,
    validation, and export capabilities. Supports custom textures, custom curves, and
    object placement.

    Attributes:
        tile_size: Size of each tile in meters (default: 0.585)

    Example:
        >>> builder = MapBuilder(tile_size=0.585)
        >>> builder.add_tile(0, 0, 'straight', 'N')
        >>> builder.add_tile(1, 0, 'curve_left', 'N')
        >>> builder.add_object('duckie1', 'duckie', pos=[1.5, 2.0])
        >>> map_data = builder.build()
    """

    # Valid tile types
    VALID_TILE_KINDS = {
        "straight",
        "curve_left",
        "curve_right",
        "3way_left",
        "3way_right",
        "4way",
        "asphalt",
        "grass",
        "floor",
        "empty",
    }

    # Valid orientations
    VALID_ORIENTATIONS = {"N", "S", "E", "W"}

    # Valid object types (common ones, not exhaustive)
    VALID_OBJECT_KINDS = {
        "duckie",
        "duckiebot",
        "cone",
        "barrier",
        "tree",
        "house",
        "bus",
        "truck",
        "sign_stop",
        "sign_yield",
        "sign_left_T_intersect",
        "sign_right_T_intersect",
        "sign_T_intersect",
        "sign_4_way_intersect",
        "sign_pedestrian",
        "sign_parking",
        "sign_no_left_turn",
        "sign_no_right_turn",
        "sign_oneway_right",
        "sign_oneway_left",
        "sign_duck_crossing",
        "sign_t_light_ahead",
        "building",
    }

    def __init__(self, tile_size: float = 0.585):
        """
        Initialize a new map builder.

        Args:
            tile_size: Size of each tile in meters (default: 0.585, standard Duckietown size)

        Raises:
            ValueError: If tile_size is not positive
        """
        if tile_size <= 0:
            raise ValueError(f"tile_size must be positive, got {tile_size}")

        self.tile_size = tile_size
        self._tiles: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self._objects: Dict[str, Dict[str, Any]] = {}
        self._start_tile: Optional[Tuple[int, int]] = None
        self._start_pose: Optional[List[float]] = None
        self._custom_textures: Optional[Dict[str, Any]] = None
        self._custom_curves: Optional[Dict[str, Any]] = None

        # Track grid bounds for validation
        self._min_i = float("inf")
        self._max_i = float("-inf")
        self._min_j = float("inf")
        self._max_j = float("-inf")

    def add_tile(self, i: int, j: int, kind: str, orientation: str = "E") -> "MapBuilder":
        """
        Add a tile to the map.

        Args:
            i: Column index (0-based, increases eastward)
            j: Row index (0-based, increases southward)
            kind: Tile type (straight, curve_left, curve_right, 3way_left,
                  3way_right, 4way, asphalt, grass, floor, empty)
            orientation: Tile orientation (N, S, E, W) (default: E)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If orientation invalid, tile kind invalid, or tile already exists

        Example:
            >>> builder.add_tile(0, 0, 'straight', 'N')
            >>> builder.add_tile(1, 0, 'curve_left', 'E')
        """
        # Validate orientation
        if orientation not in self.VALID_ORIENTATIONS:
            raise ValueError(f"Invalid orientation '{orientation}'. Must be one of {self.VALID_ORIENTATIONS}")

        # Validate tile kind
        if kind not in self.VALID_TILE_KINDS:
            raise ValueError(f"Invalid tile kind '{kind}'. Must be one of {self.VALID_TILE_KINDS}")

        # Check for duplicate
        if (i, j) in self._tiles:
            raise ValueError(f"Tile already exists at position ({i}, {j})")

        # Store tile
        self._tiles[(i, j)] = {"kind": kind, "orientation": orientation}

        # Update bounds
        self._min_i = min(self._min_i, i)
        self._max_i = max(self._max_i, i)
        self._min_j = min(self._min_j, j)
        self._max_j = max(self._max_j, j)

        return self

    def add_object(
        self,
        name: str,
        kind: str,
        pos: List[float],
        rotate: float = 0,
        height: float = 0.08,
        optional: bool = False,
        static: bool = True,
    ) -> "MapBuilder":
        """
        Add an object to the map.

        Args:
            name: Unique object identifier
            kind: Object type (duckie, duckiebot, cone, barrier, tree, house, sign_*, etc.)
            pos: [x, y] position in tile coordinates (will be scaled by tile_size)
            rotate: Rotation in degrees counter-clockwise (default: 0)
            height: Object height in meters (default: 0.08)
            optional: Whether object is optional for spawning (default: False)
            static: Whether object is static/immovable (default: True)

        Returns:
            Self for method chaining

        Raises:
            ValueError: If name already exists or pos format invalid

        Example:
            >>> builder.add_object('duckie1', 'duckie', pos=[1.5, 2.0], rotate=45)
            >>> builder.add_object('cone1', 'cone', pos=[2.0, 1.5])
        """
        if name in self._objects:
            raise ValueError(f"Object '{name}' already exists")

        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            raise ValueError(f"pos must be [x, y] list, got {pos}")

        if kind not in self.VALID_OBJECT_KINDS:
            # Warning, not error - allows custom objects
            pass

        self._objects[name] = {
            "kind": kind,
            "pos": list(pos),
            "rotate": rotate,
            "height": height,
            "optional": optional,
            "static": static,
        }

        return self

    def set_start_tile(self, tile: Union[Tuple[int, int], List[int]]) -> "MapBuilder":
        """
        Set the starting tile for the robot.

        Args:
            tile: [i, j] coordinates of start tile

        Returns:
            Self for method chaining

        Raises:
            ValueError: If tile format invalid

        Example:
            >>> builder.set_start_tile([0, 0])
            >>> builder.set_start_tile((1, 1))
        """
        if not isinstance(tile, (list, tuple)) or len(tile) != 2:
            raise ValueError(f"tile must be [i, j] coordinates, got {tile}")

        self._start_tile = tuple(tile)
        return self

    def set_start_pose(self, pose: List[float]) -> "MapBuilder":
        """
        Set explicit starting pose [x, y, angle].

        Args:
            pose: [x, y, angle_radians] starting pose

        Returns:
            Self for method chaining

        Raises:
            ValueError: If pose format invalid

        Example:
            >>> import math
            >>> builder.set_start_pose([1.5, 1.5, math.pi/2])  # Center of tile, facing north
        """
        if not isinstance(pose, (list, tuple)) or len(pose) != 3:
            raise ValueError(f"pose must be [x, y, angle] list, got {pose}")

        self._start_pose = list(pose)
        return self

    def set_custom_texture(self, i: int, j: int, texture_path: str) -> "MapBuilder":
        """
        Set custom texture for specific tile.

        Args:
            i: Column index
            j: Row index
            texture_path: Path to texture file (relative to map directory or absolute)

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_custom_texture(0, 0, 'textures/my_road.png')
        """
        if self._custom_textures is None:
            self._custom_textures = {"tile_overrides": {}}
        elif "tile_overrides" not in self._custom_textures:
            self._custom_textures["tile_overrides"] = {}

        self._custom_textures["tile_overrides"][f"[{i},{j}]"] = texture_path
        return self

    def set_global_texture(self, tile_kind: str, texture_path: str) -> "MapBuilder":
        """
        Set custom texture for all tiles of a kind.

        Args:
            tile_kind: Tile type (straight, curve_left, etc.)
            texture_path: Path to texture file

        Returns:
            Self for method chaining

        Example:
            >>> builder.set_global_texture('straight', 'textures/road.png')
            >>> builder.set_global_texture('curve_left', 'textures/curve.png')
        """
        if self._custom_textures is None:
            self._custom_textures = {"global": {}}
        elif "global" not in self._custom_textures:
            self._custom_textures["global"] = {}

        self._custom_textures["global"][tile_kind] = texture_path
        return self

    def set_custom_curves(self, i: int, j: int, curves: List[List[List[float]]]) -> "MapBuilder":
        """
        Set custom Bézier curves for a tile.

        Args:
            i: Column index
            j: Row index
            curves: List of curves, each curve is 4 control points [[x, y, z], ...]

        Returns:
            Self for method chaining

        Raises:
            ValueError: If curve format invalid (not 4 control points per curve)

        Example:
            >>> builder.set_custom_curves(0, 0, [
            ...     [[-0.2, 0, -0.5], [-0.2, 0, -0.25],
            ...      [-0.2, 0, 0.25], [-0.2, 0, 0.5]]
            ... ])
        """
        # Validate curve format
        for idx, curve in enumerate(curves):
            if len(curve) != 4:
                raise ValueError(f"Curve {idx} must have exactly 4 control points, got {len(curve)}")
            for pt_idx, point in enumerate(curve):
                if len(point) != 3:
                    raise ValueError(f"Curve {idx} control point {pt_idx} must be [x, y, z], got {point}")

        if self._custom_curves is None:
            self._custom_curves = {}

        self._custom_curves[f"[{i},{j}]"] = {
            "type": "bezier",
            "curves": [{"control_points": curve} for curve in curves],
        }

        return self

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the map before building.

        Returns:
            (is_valid, errors): Tuple of validation result and list of error messages

        Example:
            >>> builder = MapBuilder()
            >>> is_valid, errors = builder.validate()
            >>> if not is_valid:
            ...     print("Errors:", errors)
        """
        errors = []

        # Check if any tiles exist
        if not self._tiles:
            errors.append("Map has no tiles")
            return (False, errors)

        # Check for rectangular grid (all rows same width)
        grid = self._to_grid()
        row_widths = [len(row) for row in grid]
        if len(set(row_widths)) > 1:
            errors.append(f"Grid is not rectangular. Row widths: {row_widths}")

        # Validate start_tile exists if specified
        if self._start_tile is not None:
            if self._start_tile not in self._tiles:
                errors.append(f"Start tile {self._start_tile} does not exist in map")

        # Validate objects have valid positions
        for obj_name, obj_data in self._objects.items():
            pos = obj_data["pos"]
            if len(pos) != 2:
                errors.append(f"Object '{obj_name}' has invalid position (must be [x, y])")

        return (len(errors) == 0, errors)

    def _to_grid(self) -> List[List[str]]:
        """
        Convert sparse tile dict to 2D grid for YAML export.

        Returns:
            2D list of tile strings in format "kind/orientation"
        """
        if not self._tiles:
            return [[]]

        width = int(self._max_i - self._min_i + 1)
        height = int(self._max_j - self._min_j + 1)

        # Initialize grid with empty tiles
        grid = [["empty" for _ in range(width)] for _ in range(height)]

        # Fill in tiles
        for (i, j), tile in self._tiles.items():
            # Normalize to 0-based grid
            grid_i = int(i - self._min_i)
            grid_j = int(j - self._min_j)

            kind = tile["kind"]
            orient = tile["orientation"]
            grid[grid_j][grid_i] = f"{kind}/{orient}"

        return grid

    def build(self) -> Dict[str, Any]:
        """
        Build the map data structure.

        Returns:
            Dict compatible with DuckietownEnv map_data parameter

        Raises:
            ValueError: If validation fails

        Example:
            >>> builder = MapBuilder()
            >>> builder.add_tile(0, 0, 'straight', 'N')
            >>> map_data = builder.build()
            >>> from gym_duckietown.envs import DuckietownEnv
            >>> env = DuckietownEnv(map_data=map_data)
        """
        # Validate
        is_valid, errors = self.validate()
        if not is_valid:
            raise ValueError(f"Map validation failed: {', '.join(errors)}")

        # Build map data
        map_data: Dict[str, Any] = {
            "tiles": self._to_grid(),
            "tile_size": self.tile_size,
        }

        # Add optional fields
        if self._objects:
            map_data["objects"] = copy.deepcopy(self._objects)

        if self._start_tile:
            map_data["start_tile"] = list(self._start_tile)

        if self._start_pose:
            map_data["start_pose"] = self._start_pose

        if self._custom_textures:
            map_data["custom_textures"] = copy.deepcopy(self._custom_textures)

        if self._custom_curves:
            map_data["custom_curves"] = copy.deepcopy(self._custom_curves)

        return map_data

    @staticmethod
    def save_yaml(map_data: Dict[str, Any], filepath: Union[str, Path]) -> None:
        """
        Save map data to YAML file.

        Args:
            map_data: Map data dict (from build())
            filepath: Output file path

        Example:
            >>> builder = MapBuilder.create_loop(size=4)
            >>> map_data = builder.build()
            >>> MapBuilder.save_yaml(map_data, 'my_map.yaml')
        """
        filepath = Path(filepath)
        # Create parent directory if it doesn't exist
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(map_data, f, default_flow_style=False, sort_keys=False)

    # === Template Methods ===

    @classmethod
    def create_loop(
        cls, size: int = 3, tile_kind: str = "straight", tile_size: float = 0.585
    ) -> "MapBuilder":
        """
        Create a square loop template.

        Args:
            size: Side length of the loop (minimum 2)
            tile_kind: Tile type for straight sections (default: 'straight')
            tile_size: Tile size in meters (default: 0.585)

        Returns:
            MapBuilder with loop layout

        Raises:
            ValueError: If size < 2

        Example:
            >>> # Create 4x4 loop
            >>> map_data = MapBuilder.create_loop(size=4).build()
            >>>
            >>> # Create loop with obstacles
            >>> map_data = (MapBuilder.create_loop(size=4)
            ...     .add_object('cone1', 'cone', pos=[2.0, 2.0])
            ...     .build())
        """
        if size < 2:
            raise ValueError("Loop size must be at least 2")

        builder = cls(tile_size=tile_size)

        # Top edge (left to right)
        for i in range(size):
            if i == 0:
                builder.add_tile(i, 0, "curve_left", "W")
            elif i == size - 1:
                builder.add_tile(i, 0, "curve_left", "N")
            else:
                builder.add_tile(i, 0, tile_kind, "W")

        # Right edge (top to bottom)
        for j in range(1, size):
            if j == size - 1:
                builder.add_tile(size - 1, j, "curve_left", "E")
            else:
                builder.add_tile(size - 1, j, tile_kind, "N")

        # Bottom edge (right to left)
        for i in range(size - 2, -1, -1):
            if i == 0:
                builder.add_tile(i, size - 1, "curve_left", "S")
            else:
                builder.add_tile(i, size - 1, tile_kind, "E")

        # Left edge (bottom to top)
        for j in range(size - 2, 0, -1):
            builder.add_tile(0, j, tile_kind, "S")

        return builder

    @classmethod
    def create_straight_road(
        cls,
        length: int = 5,
        orientation: str = "N",
        tile_size: float = 0.585,
    ) -> "MapBuilder":
        """
        Create a straight road template.

        Args:
            length: Number of tiles (minimum 1)
            orientation: Road direction (N, S, E, W) (default: N)
            tile_size: Tile size in meters (default: 0.585)

        Returns:
            MapBuilder with straight road

        Raises:
            ValueError: If length < 1 or orientation invalid

        Example:
            >>> # Create north-facing road of 5 tiles
            >>> map_data = MapBuilder.create_straight_road(length=5, orientation='N').build()
            >>>
            >>> # Create east-facing road with duckies
            >>> map_data = (MapBuilder.create_straight_road(length=10, orientation='E')
            ...     .add_object('duckie1', 'duckie', pos=[5.0, 0.5])
            ...     .build())
        """
        if length < 1:
            raise ValueError("Length must be at least 1")

        if orientation not in cls.VALID_ORIENTATIONS:
            raise ValueError(f"Invalid orientation '{orientation}'. Must be one of {cls.VALID_ORIENTATIONS}")

        builder = cls(tile_size=tile_size)

        if orientation in ["N", "S"]:
            # Vertical road
            for j in range(length):
                builder.add_tile(0, j, "straight", orientation)
        else:  # E or W
            # Horizontal road
            for i in range(length):
                builder.add_tile(i, 0, "straight", orientation)

        return builder

    @classmethod
    def create_4way_intersection(cls, tile_size: float = 0.585) -> "MapBuilder":
        """
        Create a simple 4-way intersection template.

        Args:
            tile_size: Tile size in meters (default: 0.585)

        Returns:
            MapBuilder with 4-way intersection (3x3 grid)

        Example:
            >>> map_data = MapBuilder.create_4way_intersection().build()
        """
        builder = cls(tile_size=tile_size)

        # Create 3x3 grid with 4way in center
        # Top row
        builder.add_tile(0, 0, "straight", "S")
        builder.add_tile(1, 0, "straight", "S")
        builder.add_tile(2, 0, "straight", "S")

        # Middle row
        builder.add_tile(0, 1, "straight", "E")
        builder.add_tile(1, 1, "4way", "E")  # Center intersection
        builder.add_tile(2, 1, "straight", "W")

        # Bottom row
        builder.add_tile(0, 2, "straight", "N")
        builder.add_tile(1, 2, "straight", "N")
        builder.add_tile(2, 2, "straight", "N")

        return builder


# Export for convenience
__all__ = ["MapBuilder"]
