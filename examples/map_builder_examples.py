#!/usr/bin/env python3
"""
Examples of using the MapBuilder API for programmatic map construction.

This script demonstrates various use cases for the MapBuilder fluent API,
including template usage, custom object placement, and YAML export.
"""

import math
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.gym_duckietown import MapBuilder
from src.gym_duckietown.envs import DuckietownEnv


def example_1_simple_loop():
    """Example 1: Create a simple 3x3 loop using template."""
    print("=" * 60)
    print("Example 1: Simple 3x3 Loop (Template)")
    print("=" * 60)

    # Use template to create a loop
    map_data = MapBuilder.create_loop(size=3).build()

    # Create environment with the map
    env = DuckietownEnv(map_data=map_data, draw_curve=False, draw_bbox=False)

    print(f"Map created: {env.map_name}")
    print(f"Grid size: {len(env.grid)} tiles")
    print("Environment ready for training!\n")

    env.close()


def example_2_loop_with_obstacles():
    """Example 2: Loop with custom objects (duckies and cones)."""
    print("=" * 60)
    print("Example 2: Loop with Obstacles")
    print("=" * 60)

    # Create loop and add obstacles
    map_data = (
        MapBuilder.create_loop(size=4)
        .add_object("duckie1", kind="duckie", pos=[1.5, 1.5], rotate=45)
        .add_object("duckie2", kind="duckie", pos=[2.5, 2.5], rotate=135)
        .add_object("cone1", kind="cone", pos=[0.5, 2.0])
        .add_object("cone2", kind="cone", pos=[3.5, 1.0])
        .build()
    )

    env = DuckietownEnv(map_data=map_data)

    print(f"Map created with {len(env.objects)} objects")
    print(f"Objects: {list(env.objects.keys())}")
    print()

    env.close()


def example_3_custom_map_manual():
    """Example 3: Build custom map tile by tile."""
    print("=" * 60)
    print("Example 3: Custom Map (Manual Construction)")
    print("=" * 60)

    # Build a simple L-shaped road
    builder = MapBuilder(tile_size=0.585)

    # Vertical segment (north-facing)
    builder.add_tile(0, 0, "straight", "N")
    builder.add_tile(0, 1, "straight", "N")
    builder.add_tile(0, 2, "curve_left", "N")

    # Horizontal segment (east-facing)
    builder.add_tile(1, 2, "straight", "E")
    builder.add_tile(2, 2, "straight", "E")

    # Add objects
    builder.add_object("duckie1", kind="duckie", pos=[0.5, 1.5], rotate=0)
    builder.add_object("tree1", kind="tree", pos=[1.5, 1.0])

    # Set start position
    builder.set_start_tile([0, 0])

    # Validate before building
    is_valid, errors = builder.validate()
    if not is_valid:
        print(f"Validation errors: {errors}")
        return

    map_data = builder.build()
    env = DuckietownEnv(map_data=map_data)

    print("L-shaped map created successfully")
    print(f"Start tile: {builder._start_tile}")
    print()

    env.close()


def example_4_straight_road():
    """Example 4: Straight road using template."""
    print("=" * 60)
    print("Example 4: Straight Road Template")
    print("=" * 60)

    # Create north-facing straight road
    map_data = (
        MapBuilder.create_straight_road(length=10, orientation="N")
        .add_object("duckie1", kind="duckie", pos=[0.5, 5.0])
        .add_object("barrier1", kind="barrier", pos=[0.3, 7.0])
        .build()
    )

    env = DuckietownEnv(map_data=map_data)

    print("Straight road created (10 tiles)")
    print(f"Orientation: North")
    print()

    env.close()


def example_5_4way_intersection():
    """Example 5: 4-way intersection template."""
    print("=" * 60)
    print("Example 5: 4-Way Intersection")
    print("=" * 60)

    map_data = (
        MapBuilder.create_4way_intersection()
        .add_object("sign1", kind="sign_stop", pos=[1.0, 1.0], rotate=0)
        .add_object("sign2", kind="sign_stop", pos=[2.0, 1.0], rotate=90)
        .build()
    )

    env = DuckietownEnv(map_data=map_data)

    print("4-way intersection created")
    print(f"Grid size: 3x3 tiles")
    print()

    env.close()


def example_6_custom_start_pose():
    """Example 6: Set custom start pose."""
    print("=" * 60)
    print("Example 6: Custom Start Pose")
    print("=" * 60)

    # Create loop and set specific start pose
    map_data = (
        MapBuilder.create_loop(size=4)
        .set_start_pose([1.5, 1.5, math.pi / 2])  # Center, facing north
        .build()
    )

    env = DuckietownEnv(map_data=map_data)

    print(f"Start pose: {env.start_pose}")
    print()

    env.close()


def example_7_yaml_export():
    """Example 7: Export map to YAML file."""
    print("=" * 60)
    print("Example 7: YAML Export")
    print("=" * 60)

    # Build complex map
    builder = MapBuilder.create_loop(size=4)
    builder.add_object("duckie1", kind="duckie", pos=[1.5, 1.5])
    builder.add_object("duckie2", kind="duckie", pos=[2.5, 2.5])
    builder.add_object("cone1", kind="cone", pos=[0.5, 0.5])

    map_data = builder.build()

    # Export to YAML
    output_file = "/tmp/generated_map.yaml"
    MapBuilder.save_yaml(map_data, output_file)

    print(f"Map exported to: {output_file}")

    # Verify we can load it back
    env = DuckietownEnv(map_name=output_file)
    print(f"Successfully loaded map from YAML")
    print()

    env.close()


def example_8_validation():
    """Example 8: Validation and error handling."""
    print("=" * 60)
    print("Example 8: Validation and Error Handling")
    print("=" * 60)

    builder = MapBuilder()

    # Try to build without adding tiles (should fail)
    is_valid, errors = builder.validate()
    print(f"Empty map valid? {is_valid}")
    print(f"Errors: {errors}")

    # Add tiles
    builder.add_tile(0, 0, "straight", "N")
    builder.add_tile(1, 0, "straight", "N")

    # Try invalid orientation (should raise error)
    try:
        builder.add_tile(2, 0, "straight", "X")
    except ValueError as e:
        print(f"Caught expected error: {e}")

    # Try duplicate tile (should raise error)
    try:
        builder.add_tile(0, 0, "curve_left", "E")
    except ValueError as e:
        print(f"Caught expected error: {e}")

    # Now validate the good map
    is_valid, errors = builder.validate()
    print(f"\nValid map? {is_valid}")
    print()


def main():
    """Run all examples."""
    examples = [
        example_1_simple_loop,
        example_2_loop_with_obstacles,
        example_3_custom_map_manual,
        example_4_straight_road,
        example_5_4way_intersection,
        example_6_custom_start_pose,
        example_7_yaml_export,
        example_8_validation,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")
            import traceback

            traceback.print_exc()
            print()

    print("=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
