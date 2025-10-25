# coding=utf-8
"""
MapRegistry - Thread-safe registry for custom map directory discovery.

Allows users to register directories containing custom map YAML files for
auto-discovery and resolution by name instead of full path.

Example:
    >>> from gym_duckietown import register_map_dir
    >>> register_map_dir('/home/user/my_maps')
    >>> env = DuckietownEnv(map_name='my_custom_map')  # Auto-discovered
"""

import os
import threading
import yaml
from pathlib import Path
from typing import Dict, List, Optional

from . import logger


class MapRegistry:
    """
    Thread-safe singleton registry for custom map directories.

    Provides auto-discovery of map YAML files in registered directories,
    with caching and validation for performance.

    Example:
        >>> from gym_duckietown.map_registry import MapRegistry
        >>> registry = MapRegistry()
        >>> registry.register_directory('./my_maps')
        >>> path = registry.resolve_map('my_custom_loop')
        >>> print(f"Resolved to: {path}")

    Thread Safety:
        All public methods use internal locking to ensure thread-safe operation.
    """

    _instance: Optional["MapRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Thread-safe singleton instantiation."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize registry state (only once for singleton)."""
        if self._initialized:
            return
        self._initialized = True
        self._directories: List[Path] = []
        self._map_cache: Dict[str, Path] = {}
        self._cache_valid = False
        self._cache_lock = threading.Lock()

    def register_directory(self, directory: str) -> None:
        """
        Register a directory for custom map discovery.

        The directory will be scanned for .yaml files matching the map format.
        Directories are searched in registration order (first registered = highest priority).

        Args:
            directory: Absolute or relative path to directory containing map YAML files

        Raises:
            ValueError: If directory doesn't exist or is not a directory

        Example:
            >>> registry = MapRegistry()
            >>> registry.register_directory('./my_maps')
            >>> registry.register_directory('/absolute/path/to/maps')
        """
        # Resolve to absolute path
        dir_path = Path(directory).resolve()

        # Validate directory exists
        if not dir_path.exists():
            raise ValueError(f"Map directory does not exist: {directory}. Please check the path.")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        with self._cache_lock:
            # Check if already registered
            if dir_path in self._directories:
                logger.debug(f"Directory already registered: {dir_path}")
                return

            # Add to registry
            self._directories.append(dir_path)
            self._invalidate_cache()
            logger.info(f"Registered map directory: {dir_path}")

    def unregister_directory(self, directory: str) -> bool:
        """
        Remove a directory from the registry.

        Args:
            directory: Path to directory to unregister

        Returns:
            True if directory was registered and removed, False otherwise

        Example:
            >>> registry.unregister_directory('./my_maps')
            True
        """
        dir_path = Path(directory).resolve()

        with self._cache_lock:
            if dir_path in self._directories:
                self._directories.remove(dir_path)
                self._invalidate_cache()
                logger.info(f"Unregistered map directory: {dir_path}")
                return True
            return False

    def list_directories(self) -> List[Path]:
        """
        Return all registered directories.

        Returns:
            List of registered directory paths (as Path objects)

        Example:
            >>> dirs = registry.list_directories()
            >>> for d in dirs:
            ...     print(d)
        """
        with self._cache_lock:
            return list(self._directories)

    def discover_maps(self) -> Dict[str, Path]:
        """
        Scan all registered directories for map YAML files.

        Caches results for performance. Cache is invalidated when directories
        are added/removed.

        Returns:
            Dict mapping map names (without .yaml extension) to absolute file paths

        Example:
            >>> maps = registry.discover_maps()
            >>> print(maps)
            {'my_map': Path('/home/user/maps/my_map.yaml'), ...}

        Note:
            If duplicate map names exist in different directories, the first
            registered directory takes precedence (with a warning logged).
        """
        with self._cache_lock:
            # Return cached results if valid
            if self._cache_valid:
                return dict(self._map_cache)

            # Rebuild cache
            self._map_cache.clear()
            duplicate_warnings = []

            for directory in self._directories:
                try:
                    # Scan for .yaml files
                    if not directory.exists():
                        logger.warning(
                            f"Registered directory no longer exists: {directory}. " f"Skipping discovery."
                        )
                        continue

                    for filepath in directory.glob("*.yaml"):
                        # Skip if not a file (e.g., broken symlink)
                        if not filepath.is_file():
                            continue

                        # Security: Check for symlinks outside registered directory
                        try:
                            real_path = filepath.resolve(strict=True)
                            if not str(real_path).startswith(str(directory.resolve())):
                                logger.warning(
                                    f"Security: Skipping symlink outside registered directory: "
                                    f"{filepath} -> {real_path}"
                                )
                                continue
                        except (OSError, RuntimeError) as e:
                            logger.warning(f"Could not resolve symlink {filepath}: {e}")
                            continue

                        # Validate YAML format
                        if not self._validate_yaml(filepath):
                            continue

                        # Extract map name (filename without .yaml)
                        map_name = filepath.stem

                        # Check for duplicates
                        if map_name in self._map_cache:
                            duplicate_warnings.append(
                                f"Map '{map_name}' found in multiple directories:\n"
                                f"  - {self._map_cache[map_name]} (will be used)\n"
                                f"  - {filepath} (ignored)\n"
                                f"First registered directory takes precedence."
                            )
                        else:
                            self._map_cache[map_name] = filepath

                except Exception as e:
                    logger.warning(f"Error scanning directory {directory}: {e}")
                    continue

            # Log duplicate warnings after discovery completes
            for warning in duplicate_warnings:
                logger.warning(warning)

            self._cache_valid = True
            logger.debug(f"Discovered {len(self._map_cache)} custom maps")
            return dict(self._map_cache)

    def resolve_map(self, map_name: str) -> Optional[Path]:
        """
        Resolve a map name to its file path.

        Search order:
        1. Registered custom directories (in registration order)
        2. Built-in duckietown-world maps (returns None to trigger fallback)

        Args:
            map_name: Map name without .yaml extension

        Returns:
            Absolute path to map file, or None if not found in custom directories

        Example:
            >>> path = registry.resolve_map('my_custom_loop')
            >>> if path:
            ...     print(f"Found custom map: {path}")
            ... else:
            ...     print("Not in custom maps, will check built-in")

        Note:
            Returns None (not error) if map not found in custom directories,
            allowing caller to fall back to built-in maps.
        """
        # Ensure cache is populated
        maps = self.discover_maps()

        # Look up in cache
        return maps.get(map_name)

    def list_custom_maps(self) -> List[str]:
        """
        Return names of all discovered custom maps.

        Returns:
            List of map names (without .yaml extension)

        Example:
            >>> maps = registry.list_custom_maps()
            >>> print("Available custom maps:", maps)
            ['my_loop', 'racing_track', 'obstacle_course']
        """
        maps = self.discover_maps()
        return sorted(maps.keys())

    def clear(self) -> None:
        """
        Clear all registered directories and cache.

        Example:
            >>> registry.clear()
            >>> assert len(registry.list_directories()) == 0
        """
        with self._cache_lock:
            self._directories.clear()
            self._invalidate_cache()
            logger.debug("Cleared map registry")

    def _invalidate_cache(self) -> None:
        """Mark cache as invalid (call after directory changes)."""
        self._cache_valid = False
        self._map_cache.clear()

    def _validate_yaml(self, filepath: Path) -> bool:
        """
        Quick validation that file is a valid map YAML.

        Checks:
        - File is readable
        - Valid YAML syntax
        - Has required fields (tiles, tile_size)

        Args:
            filepath: Path to YAML file to validate

        Returns:
            True if appears to be valid map, False otherwise
        """
        try:
            # Check file is readable
            if not os.access(filepath, os.R_OK):
                logger.warning(f"Map file is not readable: {filepath}")
                return False

            # Parse YAML
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)

            # Check for required fields
            if not isinstance(data, dict):
                logger.warning(
                    f"Skipping invalid map file: {filepath}\n" f"Reason: Root element is not a dictionary"
                )
                return False

            if "tiles" not in data:
                logger.warning(
                    f"Skipping invalid map file: {filepath}\n" f"Reason: Missing required field 'tiles'"
                )
                return False

            if "tile_size" not in data:
                logger.warning(
                    f"Skipping invalid map file: {filepath}\n" f"Reason: Missing required field 'tile_size'"
                )
                return False

            # Optional: Use map_schema validator if available
            try:
                from .map_schema import validate_map_data

                is_valid, errors, warnings = validate_map_data(data, str(filepath))
                if not is_valid:
                    logger.warning(f"Skipping invalid map file: {filepath}\n" f"Validation errors: {errors}")
                    return False
                if warnings:
                    for warning in warnings:
                        logger.debug(f"Map validation warning for {filepath}: {warning}")
            except ImportError:
                # map_schema not available, skip advanced validation
                pass

            return True

        except yaml.YAMLError as e:
            logger.warning(f"Skipping invalid map file: {filepath}\nReason: Invalid YAML syntax: {e}")
            return False
        except PermissionError:
            logger.warning(f"Permission denied reading map file: {filepath}")
            return False
        except Exception as e:
            logger.warning(f"Error validating map file {filepath}: {e}")
            return False


# Module-level convenience functions using global singleton
_global_registry = MapRegistry()


def register_map_dir(directory: str) -> None:
    """
    Register a directory for custom map discovery (module-level convenience).

    Args:
        directory: Path to directory containing map YAML files

    Raises:
        ValueError: If directory doesn't exist

    Example:
        >>> import gym_duckietown
        >>> gym_duckietown.register_map_dir('./my_maps')
        >>> env = DuckietownEnv(map_name='my_custom_map')
    """
    _global_registry.register_directory(directory)


def unregister_map_dir(directory: str) -> bool:
    """
    Unregister a directory.

    Args:
        directory: Path to directory to unregister

    Returns:
        True if directory was registered and removed, False otherwise
    """
    return _global_registry.unregister_directory(directory)


def list_map_dirs() -> List[Path]:
    """
    List all registered directories.

    Returns:
        List of registered directory paths
    """
    return _global_registry.list_directories()


def list_custom_maps() -> List[str]:
    """
    List all discovered custom maps.

    Returns:
        List of map names (without .yaml extension)

    Example:
        >>> maps = gym_duckietown.list_custom_maps()
        >>> print("Available:", maps)
    """
    return _global_registry.list_custom_maps()


def resolve_map(map_name: str) -> Optional[Path]:
    """
    Resolve map name to file path.

    Args:
        map_name: Map name without .yaml extension

    Returns:
        Absolute path to map file, or None if not found
    """
    return _global_registry.resolve_map(map_name)


def clear_map_registry() -> None:
    """
    Clear all registered directories.

    Example:
        >>> gym_duckietown.clear_map_registry()
    """
    _global_registry.clear()
