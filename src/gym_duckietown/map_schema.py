"""
YAML Schema Validation for Custom Textures and Bézier Curves

This module provides validation for extended Duckietown map YAML files that support
custom textures and custom Bézier curves. All custom fields are optional, ensuring
backward compatibility with existing map files.

Schema Extensions:
    - custom_textures: Global and per-tile texture overrides
    - custom_curves: Per-tile Bézier curve definitions with control points

Example Valid YAML:
    tiles:
      - [asphalt, straight, curve_left]
      - [straight, floor, curve_right]

    objects:
      - kind: duckie
        pos: [1, 0.5]

    tile_size: 0.585

    custom_textures:
      global:
        straight: textures/my_road.png
        curve_left: textures/my_curve.png
      tile_overrides:
        "[1,2]": textures/special_tile.png

    custom_curves:
      "[0,1]":
        type: bezier
        curves:
          - control_points:
              - [-0.20, 0, -0.50]
              - [-0.20, 0, -0.25]
              - [-0.20, 0, 0.25]
              - [-0.20, 0, 0.50]
"""

from typing import Any, Dict, List, Optional, Tuple
import os
import re


# Validation result type: (is_valid, error_messages, warnings)
ValidationResult = Tuple[bool, List[str], List[str]]


def validate_map_data(map_data: Dict[str, Any], map_file_path: Optional[str] = None) -> ValidationResult:
    """
    Validate map YAML data including optional custom extensions.

    Validates both standard map fields (tiles, objects) and custom extensions
    (custom_textures, custom_curves). All custom fields are optional for
    backward compatibility.

    Args:
        map_data: Parsed YAML dict with tiles, objects, and optional custom fields
        map_file_path: Optional path to map YAML file for resolving relative texture paths

    Returns:
        Tuple of (is_valid, error_messages, warnings):
            - is_valid: True if validation passes (no errors)
            - error_messages: List of validation errors (empty if valid)
            - warnings: List of non-critical warnings (e.g., missing texture files)

    Example:
        >>> data = yaml.load(open("map.yaml"))
        >>> valid, errors, warnings = validate_map_data(data, "maps/map.yaml")
        >>> if not valid:
        >>>     print("Errors:", "\\n".join(errors))
        >>> if warnings:
        >>>     print("Warnings:", "\\n".join(warnings))
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Validate required base fields
    if "tiles" not in map_data:
        errors.append("Missing required field 'tiles'")
    elif not isinstance(map_data["tiles"], list):
        errors.append("Field 'tiles' must be a list")
    else:
        # Validate tiles is 2D array
        for i, row in enumerate(map_data["tiles"]):
            if not isinstance(row, list):
                errors.append(f"tiles[{i}]: Expected list, got {type(row).__name__}")

    # Validate optional custom_textures
    if "custom_textures" in map_data:
        tex_valid, tex_errors, tex_warnings = validate_custom_textures(
            map_data["custom_textures"], map_file_path
        )
        errors.extend(tex_errors)
        warnings.extend(tex_warnings)

    # Validate optional custom_curves
    if "custom_curves" in map_data:
        curve_valid, curve_errors, curve_warnings = validate_custom_curves(map_data["custom_curves"])
        errors.extend(curve_errors)
        warnings.extend(curve_warnings)

    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)


def validate_custom_textures(custom_textures: Any, map_file_path: Optional[str] = None) -> ValidationResult:
    """
    Validate custom_textures section of map YAML.

    Schema:
        custom_textures:
          global:              # Optional: applies to all tiles of given kind
            <tile_kind>: <path>
          tile_overrides:      # Optional: applies to specific coordinates
            "[i,j]": <path>

    Args:
        custom_textures: The custom_textures dict from map YAML
        map_file_path: Optional path to map file for resolving relative paths

    Returns:
        Tuple of (is_valid, errors, warnings)

    Example:
        >>> textures = {
        ...     "global": {"straight": "textures/road.png"},
        ...     "tile_overrides": {"[1,2]": "textures/special.png"}
        ... }
        >>> valid, errors, warnings = validate_custom_textures(textures)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(custom_textures, dict):
        errors.append(f"custom_textures: Expected dict, got {type(custom_textures).__name__}")
        return (False, errors, warnings)

    # Get map directory for resolving relative paths
    map_dir = None
    if map_file_path:
        map_dir = os.path.dirname(os.path.abspath(map_file_path))

    # Validate global textures
    if "global" in custom_textures:
        global_textures = custom_textures["global"]
        if not isinstance(global_textures, dict):
            errors.append(f"custom_textures.global: Expected dict, got {type(global_textures).__name__}")
        else:
            for tile_kind, texture_path in global_textures.items():
                if not isinstance(tile_kind, str):
                    errors.append(
                        f"custom_textures.global: Key must be string, got {type(tile_kind).__name__}"
                    )
                if not isinstance(texture_path, str):
                    errors.append(
                        f"custom_textures.global['{tile_kind}']: Expected string path, got {type(texture_path).__name__}"
                    )
                else:
                    # Check if file exists (warning only)
                    if map_dir:
                        full_path = _resolve_path(texture_path, map_dir)
                        if not os.path.exists(full_path):
                            warnings.append(
                                f"custom_textures.global['{tile_kind}']: File not found: {full_path}"
                            )

    # Validate tile_overrides
    if "tile_overrides" in custom_textures:
        tile_overrides = custom_textures["tile_overrides"]
        if not isinstance(tile_overrides, dict):
            errors.append(
                f"custom_textures.tile_overrides: Expected dict, got {type(tile_overrides).__name__}"
            )
        else:
            for coords, texture_path in tile_overrides.items():
                # Validate coordinate format "[i,j]"
                if not _validate_coord_format(coords):
                    errors.append(
                        f"custom_textures.tile_overrides: Invalid coordinate format '{coords}', expected '[i,j]'"
                    )

                if not isinstance(texture_path, str):
                    errors.append(
                        f"custom_textures.tile_overrides['{coords}']: Expected string path, got {type(texture_path).__name__}"
                    )
                else:
                    # Check if file exists (warning only)
                    if map_dir:
                        full_path = _resolve_path(texture_path, map_dir)
                        if not os.path.exists(full_path):
                            warnings.append(
                                f"custom_textures.tile_overrides['{coords}']: File not found: {full_path}"
                            )

    # Check for unknown keys
    valid_keys = {"global", "tile_overrides"}
    for key in custom_textures.keys():
        if key not in valid_keys:
            warnings.append(f"custom_textures: Unknown key '{key}', expected one of {valid_keys}")

    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)


def validate_custom_curves(custom_curves: Any) -> ValidationResult:
    """
    Validate custom_curves section of map YAML.

    Schema:
        custom_curves:
          "[i,j]":               # Tile coordinates
            type: bezier         # Currently only "bezier" supported
            curves:              # List of curve definitions
              - control_points:  # List of 4 3D points [x, y, z]
                  - [-0.20, 0, -0.50]
                  - [-0.20, 0, -0.25]
                  - [-0.20, 0, 0.25]
                  - [-0.20, 0, 0.50]

    Args:
        custom_curves: The custom_curves dict from map YAML

    Returns:
        Tuple of (is_valid, errors, warnings)

    Example:
        >>> curves = {
        ...     "[0,1]": {
        ...         "type": "bezier",
        ...         "curves": [{
        ...             "control_points": [
        ...                 [-0.20, 0, -0.50],
        ...                 [-0.20, 0, -0.25],
        ...                 [-0.20, 0, 0.25],
        ...                 [-0.20, 0, 0.50]
        ...             ]
        ...         }]
        ...     }
        ... }
        >>> valid, errors, warnings = validate_custom_curves(curves)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(custom_curves, dict):
        errors.append(f"custom_curves: Expected dict, got {type(custom_curves).__name__}")
        return (False, errors, warnings)

    for coords, curve_def in custom_curves.items():
        # Validate coordinate format "[i,j]"
        if not _validate_coord_format(coords):
            errors.append(f"custom_curves: Invalid coordinate format '{coords}', expected '[i,j]'")
            continue

        if not isinstance(curve_def, dict):
            errors.append(f"custom_curves['{coords}']: Expected dict, got {type(curve_def).__name__}")
            continue

        # Validate type field
        if "type" not in curve_def:
            errors.append(f"custom_curves['{coords}']: Missing required field 'type'")
        elif curve_def["type"] != "bezier":
            errors.append(f"custom_curves['{coords}'].type: Expected 'bezier', got '{curve_def['type']}'")

        # Validate curves list
        if "curves" not in curve_def:
            errors.append(f"custom_curves['{coords}']: Missing required field 'curves'")
            continue

        curves_list = curve_def["curves"]
        if not isinstance(curves_list, list):
            errors.append(
                f"custom_curves['{coords}'].curves: Expected list, got {type(curves_list).__name__}"
            )
            continue

        if len(curves_list) == 0:
            warnings.append(f"custom_curves['{coords}'].curves: Empty curves list")

        # Validate each curve
        for curve_idx, curve in enumerate(curves_list):
            if not isinstance(curve, dict):
                errors.append(
                    f"custom_curves['{coords}'].curves[{curve_idx}]: Expected dict, got {type(curve).__name__}"
                )
                continue

            # Validate control_points
            if "control_points" not in curve:
                errors.append(
                    f"custom_curves['{coords}'].curves[{curve_idx}]: Missing required field 'control_points'"
                )
                continue

            cp_valid, cp_errors, cp_warnings = validate_control_points(
                curve["control_points"], f"custom_curves['{coords}'].curves[{curve_idx}]"
            )
            errors.extend(cp_errors)
            warnings.extend(cp_warnings)

    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)


def validate_control_points(control_points: Any, context: str = "control_points") -> ValidationResult:
    """
    Validate Bézier curve control points.

    Requirements:
        - Must be a list of exactly 4 points
        - Each point must be a list of 3 numbers [x, y, z]
        - Coordinates should be in normalized tile space [-0.5, 0.5]
        - Y coordinate should typically be 0 (ground level)

    Args:
        control_points: List of control points to validate
        context: Context string for error messages (e.g., "custom_curves['[0,1]'].curves[0]")

    Returns:
        Tuple of (is_valid, errors, warnings)

    Example:
        >>> points = [
        ...     [-0.20, 0, -0.50],
        ...     [-0.20, 0, -0.25],
        ...     [-0.20, 0, 0.25],
        ...     [-0.20, 0, 0.50]
        ... ]
        >>> valid, errors, warnings = validate_control_points(points)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if not isinstance(control_points, list):
        errors.append(f"{context}.control_points: Expected list, got {type(control_points).__name__}")
        return (False, errors, warnings)

    # Check for exactly 4 control points
    if len(control_points) != 4:
        errors.append(f"{context}.control_points: Expected 4 control points, got {len(control_points)}")
        return (False, errors, warnings)

    # Validate each point
    for pt_idx, point in enumerate(control_points):
        if not isinstance(point, list):
            errors.append(f"{context}.control_points[{pt_idx}]: Expected list, got {type(point).__name__}")
            continue

        # Check for exactly 3 coordinates [x, y, z]
        if len(point) != 3:
            errors.append(
                f"{context}.control_points[{pt_idx}]: Expected 3 coordinates [x, y, z], got {len(point)}"
            )
            continue

        # Validate each coordinate is a number
        for coord_idx, coord in enumerate(point):
            coord_name = ["x", "y", "z"][coord_idx]
            if not isinstance(coord, (int, float)):
                errors.append(
                    f"{context}.control_points[{pt_idx}][{coord_name}]: Expected number, got {type(coord).__name__}"
                )
            else:
                # Check coordinate is in reasonable range
                if abs(coord) > 10.0:
                    warnings.append(
                        f"{context}.control_points[{pt_idx}][{coord_name}]: Value {coord} is outside typical range [-10, 10]"
                    )

                # Warn if coordinates are far outside normalized tile space
                if coord_idx != 1 and abs(coord) > 0.5:  # x and z (not y)
                    warnings.append(
                        f"{context}.control_points[{pt_idx}][{coord_name}]: Value {coord} is outside normalized tile space [-0.5, 0.5]"
                    )

                # Warn if Y coordinate is not 0 (ground level)
                if coord_idx == 1 and coord != 0:
                    warnings.append(
                        f"{context}.control_points[{pt_idx}].y: Non-zero Y coordinate {coord} (expected 0 for ground level)"
                    )

    is_valid = len(errors) == 0
    return (is_valid, errors, warnings)


def _validate_coord_format(coords: str) -> bool:
    """
    Validate coordinate string format "[i,j]" where i and j are integers.

    Args:
        coords: Coordinate string to validate

    Returns:
        True if format is valid, False otherwise

    Example:
        >>> _validate_coord_format("[1,2]")
        True
        >>> _validate_coord_format("[0,0]")
        True
        >>> _validate_coord_format("1,2")
        False
        >>> _validate_coord_format("[a,b]")
        False
    """
    # Match pattern: [integer,integer]
    pattern = r"^\[\s*-?\d+\s*,\s*-?\d+\s*\]$"
    return bool(re.match(pattern, coords))


def _resolve_path(relative_path: str, base_dir: str) -> str:
    """
    Resolve a relative path against a base directory.

    Args:
        relative_path: Path to resolve (absolute or relative)
        base_dir: Base directory for relative paths

    Returns:
        Absolute path

    Example:
        >>> _resolve_path("textures/road.png", "/home/user/maps")
        '/home/user/maps/textures/road.png'
        >>> _resolve_path("/absolute/path.png", "/home/user/maps")
        '/absolute/path.png'
    """
    if os.path.isabs(relative_path):
        return relative_path
    return os.path.abspath(os.path.join(base_dir, relative_path))


def format_validation_report(is_valid: bool, errors: List[str], warnings: List[str]) -> str:
    """
    Format validation results as a human-readable report.

    Args:
        is_valid: Whether validation passed
        errors: List of error messages
        warnings: List of warning messages

    Returns:
        Formatted report string

    Example:
        >>> valid, errors, warnings = validate_map_data(data)
        >>> print(format_validation_report(valid, errors, warnings))
        Map Validation: PASSED

        Warnings (2):
          - custom_textures.global['straight']: File not found: /path/to/texture.png
          - custom_curves['[0,1]'].curves[0].control_points[3].z: Value 1.5 is outside normalized tile space [-0.5, 0.5]
    """
    lines = []

    # Header
    status = "PASSED" if is_valid else "FAILED"
    lines.append(f"Map Validation: {status}")
    lines.append("")

    # Errors
    if errors:
        lines.append(f"Errors ({len(errors)}):")
        for error in errors:
            lines.append(f"  - {error}")
        lines.append("")

    # Warnings
    if warnings:
        lines.append(f"Warnings ({len(warnings)}):")
        for warning in warnings:
            lines.append(f"  - {warning}")
        lines.append("")

    # Summary
    if is_valid and not warnings:
        lines.append("No issues found.")

    return "\n".join(lines)


# Convenience function for quick validation
def validate_map_file(map_file_path: str) -> ValidationResult:
    """
    Validate a map YAML file.

    Args:
        map_file_path: Path to map YAML file

    Returns:
        Tuple of (is_valid, errors, warnings)

    Raises:
        FileNotFoundError: If map file doesn't exist
        yaml.YAMLError: If YAML parsing fails

    Example:
        >>> valid, errors, warnings = validate_map_file("maps/custom_map.yaml")
        >>> if not valid:
        >>>     print("Invalid map:", errors)
    """
    import yaml

    if not os.path.exists(map_file_path):
        raise FileNotFoundError(f"Map file not found: {map_file_path}")

    with open(map_file_path, "r") as f:
        map_data = yaml.safe_load(f)

    return validate_map_data(map_data, map_file_path)
