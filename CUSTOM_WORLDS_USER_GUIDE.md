# Custom Worlds User Guide
## Gym-Duckietown

Complete guide for creating and using custom maps, textures, and Bézier curves in gym-duckietown.

**Version:** 6.2.0
**Last Updated:** October 2025

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Introduction](#introduction)
3. [Custom Textures](#custom-textures)
4. [Custom Bézier Curves](#custom-bezier-curves)
5. [MapRegistry System](#mapregistry-system)
6. [MapBuilder API](#mapbuilder-api)
7. [Complete Examples](#complete-examples)
8. [Troubleshooting](#troubleshooting)
9. [FAQ](#faq)
10. [Quick Reference](#quick-reference)

---

## Quick Start

### Method 1: Load Existing Custom Map (30 seconds)

```python
from gym_duckietown.envs import DuckietownEnv

# Load custom map by file path
env = DuckietownEnv(map_name='examples/custom_maps/demo_racing_track.yaml')
env.reset()
env.render('human')
```

### Method 2: Create Map with MapBuilder (2 minutes)

```python
from gym_duckietown import MapBuilder
from gym_duckietown.envs import DuckietownEnv

# Create a 4×4 loop programmatically
map_data = (MapBuilder.create_loop(size=4)
    .add_object('duckie1', 'duckie', pos=[2.0, 2.0])
    .build())

env = DuckietownEnv(map_data=map_data)
env.reset()
```

### Method 3: Register Map Directory (1 minute)

```python
import gym_duckietown
from gym_duckietown.envs import DuckietownEnv

# Register directory once
gym_duckietown.register_map_dir('./my_maps')

# Use maps by name
env = DuckietownEnv(map_name='my_custom_loop')
```


## Introduction

### What Are Custom Worlds?

Custom worlds allow you to create unique Duckietown environments with:

- **Custom Textures**: Replace road/tile textures with your own designs
- **Custom Bézier Curves**: Modify lane-following paths for different driving behaviors
- **Map Registry**: Organize and auto-discover custom maps in directories
- **Programmatic Construction**: Build maps with Python code using MapBuilder API

### Key Features

✨ **Three Ways to Create Maps:**
1. **YAML Files** - Hand-edit map layout and properties
2. **MapRegistry** - Organize maps in directories, load by name
3. **MapBuilder API** - Build maps programmatically with Python

🎨 **Full Customization:**
- Per-tile or global texture overrides
- Custom Bézier curves for lane geometry
- Object placement and configuration
- Starting positions and poses

---

## Custom Textures

### Overview

Replace default road textures with your own images for:
- Racing tracks with stripes
- Night/day variations
- Seasonal themes
- Training domain randomization

### YAML Format

**Global Override** (all tiles of a type):
```yaml
tiles:
  - [straight/N, curve_left/N]
  - [straight/S, straight/E]

tile_size: 0.585

custom_textures:
  global:
    straight: "textures/my_road.png"
    curve_left: "textures/my_curve.png"
```

**Tile-Specific Override** (individual tiles):
```yaml
custom_textures:
  tile_overrides:
    "[0,0]": "textures/start_line.png"
    "[1,0]": "textures/finish_line.png"
```

**Combined** (tile overrides take priority):
```yaml
custom_textures:
  global:
    straight: "textures/default_road.png"
  tile_overrides:
    "[0,0]": "textures/special_start.png"  # This tile gets special texture
```

### Three-Tier Fallback System

The simulator checks textures in this order:

1. **Tile-specific override** (`tile_overrides["[i,j]"]`) - Highest priority
2. **Global override** (`global[tile_kind]`) - Medium priority
3. **Default texture** (from duckietown-world) - Fallback

If any step fails (file missing, invalid format), it falls back to the next level with a warning.

### Texture Requirements

**Formats:**
- PNG (recommended for transparency)
- JPG/JPEG (for photos)

**Dimensions:**
- **Recommended**: 512×512 or 1024×1024
- Must be power of 2 for optimal GPU performance
- Maximum: 2048×2048 (larger impacts performance)

**Properties:**
- **Tileable**: Edges should seamlessly connect
- **Aspect ratio**: 1:1 (square)
- **Color space**: RGB or RGBA

### Path Resolution

**Relative paths** (recommended for portability):
```yaml
custom_textures:
  global:
    straight: "textures/road.png"  # Relative to YAML file
```

**Absolute paths**:
```yaml
custom_textures:
  global:
    straight: "/home/user/textures/road.png"  # Full path
```

### Creating Textures


#### Method 1: GIMP/Photoshop

1. Create 512×512 image
2. Design your texture
3. Make edges seamless: **Filters → Map → Make Seamless** (GIMP)
4. Export as PNG

#### Method 2: Python (PIL)

```python
from PIL import Image

# Create solid color with stripes
img = Image.new('RGB', (512, 512), color=(80, 80, 80))
pixels = img.load()

# Add white edges
for i in range(512):
    for j in range(50):  # Top/bottom stripes
        pixels[i, j] = (255, 255, 255)
        pixels[i, 512-j-1] = (255, 255, 255)

img.save('my_road.png')
```

### Example: Racing Track

**Goal:** Create a racing-themed map with striped roads

**Step 1:** Create textures (or use demo)
```bash
ls examples/custom_maps/textures/
# racing_straight.png  racing_asphalt.png
```

**Step 2:** Create `my_racing_track.yaml`
```yaml
tiles:
  - [straight/N, straight/N, curve_left/N]
  - [straight/S, asphalt, straight/N]
  - [curve_left/S, straight/E, curve_left/E]

tile_size: 0.585

custom_textures:
  global:
    straight: "textures/racing_straight.png"
    asphalt: "textures/racing_asphalt.png"

objects:
  cone1:
    kind: cone
    pos: [1.5, 1.5]
```

**Step 3:** Load and test
```python
from gym_duckietown.envs import DuckietownEnv

env = DuckietownEnv(
    map_name='my_racing_track.yaml',
    domain_rand=False
)
obs = env.reset()
env.render('human')
```

**Result:** Racing stripes on straights, dark grid on asphalt ✅

### Common Texture Issues

**Problem:** Texture not loading
```
WARNING:gym-duckietown:Custom texture not found: textures/road.png, using default
```

**Solutions:**
1. Check file exists: `ls textures/road.png`
2. Verify path relative to YAML file
3. Check file permissions (readable)
4. Verify image format (PNG/JPG only)

**Problem:** Seams visible between tiles

**Solution:** Make texture tileable in image editor:
- GIMP: Filters → Map → Make Seamless
- Photoshop: Filter → Other → Offset, then clone stamp edges

---

## Custom Bézier Curves

### Overview

Bézier curves define the expected driving path for:
- Lane-following reward computation
- Visual debugging (lane markers)
- Training signals for RL agents

Customize curves to:
- Make turns wider/tighter
- Create curved "straight" sections
- Design complex intersections
- Adjust difficulty for training

### Coordinate System

**Tile-local normalized space** `[-0.5, 0.5]`:

```
        North (N)
           ↑ +Z
           |
West ←-----+-----→ East
 -X  (0,0) |  +X
           |
           ↓ -Z
        South (S)

Tile center: [0, 0, 0]
Tile edges:  ±0.5 in X and Z
Y-axis: always 0 (ground level)

Example positions:
  [-0.5,  0,    0] = West edge center
  [ 0,    0,  0.5] = North edge center
  [ 0.2,  0, -0.3] = 20% east, 30% south of center
```

**Important:** Coordinates are normalized BEFORE tile rotation and world placement.

### YAML Format

**Basic Example** (single lane):
```yaml
tiles:
  - [straight/N]

tile_size: 0.585

custom_curves:
  "[0,0]":  # Tile at grid position [i=0, j=0]
    type: "bezier"
    curves:
      # Lane 1: Left lane (4 control points)
      - control_points:
        - [-0.20, 0, -0.50]  # Start: left side, south edge
        - [-0.20, 0, -0.25]  # Control point 1
        - [-0.20, 0,  0.25]  # Control point 2
        - [-0.20, 0,  0.50]  # End: left side, north edge
```

**Two Lanes** (typical):
```yaml
custom_curves:
  "[0,0]":
    curves:
      # Lane 1 (left)
      - control_points:
        - [-0.20, 0, -0.50]
        - [-0.20, 0, -0.25]
        - [-0.20, 0,  0.25]
        - [-0.20, 0,  0.50]

      # Lane 2 (right, opposite direction)
      - control_points:
        - [ 0.20, 0,  0.50]
        - [ 0.20, 0,  0.25]
        - [ 0.20, 0, -0.25]
        - [ 0.20, 0, -0.50]
```

### Control Points

**Cubic Bézier curves** require exactly **4 control points**:

1. **Start point** - Curve begins here
2. **Control point 1** - Pulls curve toward this direction
3. **Control point 2** - Pulls curve from this direction
4. **End point** - Curve ends here

**Curve shape:**
```
Start •───────•─→     • Control 1
             ╱  ╲
           ╱      ╲
         ╱          ╲
       ╱              • Control 2
     ╱
End •

The curve is tangent to Start→Control1 at the start
and tangent to Control2→End at the end.
```

### Transformation Order

Your coordinates are transformed to world space:

1. **Scale** by `tile_size` (0.585m typically)
   ```
   [-0.2, 0, -0.5] → [-0.117, 0, -0.2925]
   ```

2. **Rotate** by tile orientation (N/S/E/W)
   ```
   N: 0°, E: 90°, S: 180°, W: 270°
   ```

3. **Translate** to tile center in world
   ```
   Tile [i,j] center = [(i+0.5)*tile_size, 0, (j+0.5)*tile_size]
   ```

### Example: Wide Turn

**Goal:** Make a curve_left tile have a wider, smoother turn

**Default curve** (tight):
```
Start [-0.20, 0, -0.50]
  CP1 [-0.20, 0,  0.00]  ← Pulls hard left
  CP2 [ 0.00, 0,  0.20]  ← Pulls hard up
End   [ 0.50, 0,  0.20]
```

**Custom curve** (wider):
```yaml
custom_curves:
  "[0,0]":  # Assuming curve_left at [0,0]
    curves:
      - control_points:
        - [-0.15, 0, -0.50]  # Start slightly more centered
        - [-0.15, 0, -0.10]  # Control 1: gentler pull
        - [-0.10, 0,  0.15]  # Control 2: gentler pull
        - [ 0.50, 0,  0.15]  # End slightly lower
```

**Result:** Smoother, more gradual turn ✅

### Debugging Curves

**Visual verification** (temporary):
```python
env = DuckietownEnv(
    map_name='my_curves.yaml',
    draw_curve=False  # Note: curve drawing disabled on macOS Metal
)
```

**Programmatic check:**
```python
env.reset()
tile = env.grid[0]  # First tile
print("Curves:", tile.get('curves'))

# Inspect control points
if tile['curves'] is not None:
    for i, curve in enumerate(tile['curves']):
        print(f"Lane {i}: {curve.shape}")  # Should be (4, 3)
```

### Common Curve Issues

**Problem:** Curves not applied
```
○ Using default Bézier curves
```

**Solutions:**
1. Check tile position is correct: `"[0,0]"` not `"[0, 0]"` (no spaces)
2. Verify 4 control points per curve
3. Check Y-coordinate is 0 (not omitted)
4. Validate YAML syntax (run `python -m yaml my_map.yaml`)

**Problem:** Robot drives off track

**Cause:** Curve doesn't match tile orientation

**Solution:** Remember curves are in tile-local space. For a `straight/W` (west-facing):
- Start should be on east edge: `[0.5, 0, ...]`
- End should be on west edge: `[-0.5, 0, ...]`

---

## MapRegistry System

### Overview

The MapRegistry allows you to:
- Register directories containing custom maps
- Auto-discover all `.yaml` files in registered directories
- Resolve map names to file paths
- Organize maps by project/theme

**Benefits:**
- No need to remember full file paths
- Easy project organization
- Shareable map directories
- Team collaboration

### Registering Directories

**Global registration** (affects all environments):
```python
import gym_duckietown

# Register single directory
gym_duckietown.register_map_dir('./my_maps')

# Register multiple directories
gym_duckietown.register_map_dir('./racing_maps')
gym_duckietown.register_map_dir('./training_maps')
gym_duckietown.register_map_dir('/shared/team_maps')
```

**Per-environment registration**:
```python
from gym_duckietown.envs import DuckietownEnv

# Register just for this environment
env = DuckietownEnv(
    map_name='my_custom_loop',
    map_dirs=['./my_maps', './backup_maps']
)
```

### Auto-Discovery

Once registered, all `.yaml` files are discovered automatically:

```python
import gym_duckietown

gym_duckietown.register_map_dir('./my_maps')

# List all discovered maps
maps = gym_duckietown.list_custom_maps()
print(maps)
# ['racing_loop', 'night_track', 'training_simple', ...]
```

**Discovery rules:**
- Scans recursively through subdirectories
- Validates YAML syntax
- Checks required fields (`tiles`, `tile_size`)
- Skips invalid files with warnings
- Caches results for performance

### Resolution Priority

When you load a map by name, the simulator searches in order:

1. **Registered custom directories** (in registration order)
2. **Built-in duckietown-world maps** (if not found in custom)

**Example:**
```python
gym_duckietown.register_map_dir('./my_maps')      # Priority 1
gym_duckietown.register_map_dir('./backup_maps')  # Priority 2

# If 'loop' exists in both directories:
env = DuckietownEnv(map_name='loop')
# Uses: ./my_maps/loop.yaml (first registered)
```

**Duplicate warning:**
```
Warning: Map 'loop' found in multiple directories:
  - ./my_maps/loop.yaml (will be used)
  - ./backup_maps/loop.yaml (ignored)
First registered directory takes precedence.
```

### API Reference

**Module-level functions:**

```python
import gym_duckietown

# Register directory
gym_duckietown.register_map_dir(directory: str)

# Unregister directory
gym_duckietown.unregister_map_dir(directory: str) -> bool

# List registered directories
dirs = gym_duckietown.list_map_dirs() -> List[Path]

# List discovered maps
maps = gym_duckietown.list_custom_maps() -> List[str]

# Resolve map name to path
path = gym_duckietown.resolve_map(map_name: str) -> Optional[Path]

# Clear all registrations
gym_duckietown.clear_map_registry()
```

**Direct registry access:**
```python
from gym_duckietown.map_registry import MapRegistry

registry = MapRegistry()  # Singleton
registry.register_directory('./maps')
all_maps = registry.discover_maps()  # Dict[name, Path]
```

### Example: Project Organization

**Directory structure:**
```
my_project/
├── maps/
│   ├── training/
│   │   ├── simple_loop.yaml
│   │   ├── medium_obstacles.yaml
│   │   └── hard_course.yaml
│   ├── testing/
│   │   ├── validation_track.yaml
│   │   └── benchmark_course.yaml
│   └── textures/
│       └── custom_road.png
└── train.py
```

**In `train.py`:**
```python
import gym_duckietown
from gym_duckietown.envs import DuckietownEnv

# Register once at startup
gym_duckietown.register_map_dir('./maps/training')

# Use maps by name throughout training
for difficulty in ['simple_loop', 'medium_obstacles', 'hard_course']:
    env = DuckietownEnv(map_name=difficulty)
    # ... training loop ...
```

---

## MapBuilder API

### Overview

Build maps programmatically with Python instead of writing YAML:

**Benefits:**
- **Procedural generation** - Create maps algorithmically
- **Parameterization** - Generate variations programmatically
- **Testing** - Easily create test scenarios
- **Validation** - Catch errors before env creation

### Basic Usage

```python
from gym_duckietown import MapBuilder
from gym_duckietown.envs import DuckietownEnv

# Create builder
builder = MapBuilder(tile_size=0.585)

# Add tiles
builder.add_tile(0, 0, 'straight', 'N')
builder.add_tile(1, 0, 'curve_left', 'N')
builder.add_tile(1, 1, 'straight', 'W')

# Add objects
builder.add_object('duckie1', 'duckie', pos=[1.5, 0.5])

# Build and use
map_data = builder.build()
env = DuckietownEnv(map_data=map_data)
```

### Fluent API

**Method chaining** for concise map creation:

```python
map_data = (MapBuilder()
    .add_tile(0, 0, 'straight', 'N')
    .add_tile(1, 0, 'curve_left', 'N')
    .add_object('duckie1', 'duckie', pos=[1.5, 0.5])
    .set_start_tile((0, 0))
    .build())
```

### Core Methods

**Tile Management:**
```python
builder.add_tile(
    i: int,              # Column index (0-based)
    j: int,              # Row index (0-based)
    kind: str,           # 'straight', 'curve_left', 'curve_right',
                         # '3way_left', '3way_right', '4way',
                         # 'asphalt', 'grass', 'floor', 'empty'
    orientation: str     # 'N', 'S', 'E', 'W' (default: 'E')
) -> MapBuilder
```

**Object Management:**
```python
builder.add_object(
    name: str,           # Unique identifier
    kind: str,           # 'duckie', 'duckiebot', 'cone', 'barrier',
                         # 'tree', 'house', 'sign_stop', etc.
    pos: List[float],    # [x, y] in tile coordinates
    rotate: float = 0,   # Degrees counter-clockwise
    height: float = 0.08,
    optional: bool = False,
    static: bool = True
) -> MapBuilder
```

**Starting Position:**
```python
builder.set_start_tile((i, j))  # Grid coordinates
builder.set_start_pose([x, y, angle])  # World coordinates + radians
```

**Custom Features:**
```python
builder.set_custom_texture(i, j, "path/to/texture.png")
builder.set_global_texture("straight", "path/to/texture.png")
builder.set_custom_curves(i, j, [
    [[-0.2, 0, -0.5], [-0.2, 0, -0.25],
     [-0.2, 0, 0.25], [-0.2, 0, 0.5]]
])
```

**Validation & Building:**
```python
is_valid, errors = builder.validate()
map_data = builder.build()  # Raises ValueError if invalid
```

### Template Methods

**Pre-built patterns** for common layouts:

**Loop:**
```python
builder = MapBuilder.create_loop(
    size=4,                    # Side length (minimum 2)
    tile_kind='straight',     # Tile for straight sections
    tile_size=0.585
)
```

**Straight Road:**
```python
builder = MapBuilder.create_straight_road(
    length=10,                # Number of tiles
    orientation='N',          # 'N', 'S', 'E', or 'W'
    tile_size=0.585
)
```

**4-Way Intersection:**
```python
builder = MapBuilder.create_4way_intersection(
    tile_size=0.585
)
```

### YAML Export

**Save to file:**
```python
map_data = builder.build()
MapBuilder.save_yaml(map_data, 'output_map.yaml')
```

**Use exported map:**
```python
# Later, load the YAML file
env = DuckietownEnv(map_name='output_map.yaml')
```

### Validation

**Built-in validation** catches errors early:

```python
builder = MapBuilder()
# ... (forget to add tiles)

map_data = builder.build()
# ValueError: Map validation failed: Map has no tiles
```

**Manual validation:**
```python
is_valid, errors = builder.validate()
if not is_valid:
    for error in errors:
        print(f"Error: {error}")
```

**Validation checks:**
- Map has at least one tile
- Grid is rectangular (all rows same width)
- Objects have valid positions
- Start tile exists (if set)
- Custom curves have correct format

### Advanced Example: Procedural Generation

```python
import random
from gym_duckietown import MapBuilder

def generate_random_loop(size, num_obstacles):
    """Generate a random loop with obstacles."""
    builder = MapBuilder.create_loop(size=size)

    # Add random obstacles inside loop
    for i in range(num_obstacles):
        # Random position within loop
        x = random.uniform(0.5, size - 0.5)
        y = random.uniform(0.5, size - 0.5)

        # Random obstacle type
        kind = random.choice(['cone', 'barrier', 'duckie'])

        builder.add_object(
            f'obstacle_{i}',
            kind=kind,
            pos=[x, y],
            rotate=random.uniform(0, 360)
        )

    return builder.build()

# Generate 5 variations for training
for i in range(5):
    map_data = generate_random_loop(size=5, num_obstacles=3)
    MapBuilder.save_yaml(map_data, f'training_loop_{i}.yaml')
```

---

## Complete Examples

### Example 1: Racing Track with Checkpoints

**Goal:** Create racing track with start/finish lines and cones

```python
from gym_duckietown import MapBuilder

# Create 5×5 loop
builder = MapBuilder.create_loop(size=5)

# Mark start line with cone
builder.add_object('start_cone_left', 'cone', pos=[0.3, 0.5])
builder.add_object('start_cone_right', 'cone', pos=[0.7, 0.5])

# Mark finish line
builder.add_object('finish_cone_left', 'cone', pos=[0.3, 4.5])
builder.add_object('finish_cone_right', 'cone', pos=[0.7, 4.5])

# Add checkpoints
builder.add_object('checkpoint1', 'barrier', pos=[4.5, 2.5])
builder.add_object('checkpoint2', 'barrier', pos=[2.5, 4.5])

# Set start position
builder.set_start_tile((0, 0))

# Build and run
map_data = builder.build()

from gym_duckietown.envs import DuckietownEnv
env = DuckietownEnv(map_data=map_data, domain_rand=False)
env.reset()
```

### Example 2: Night Mode Map (YAML)

**Goal:** Dark textures for night driving simulation

**File:** `night_track.yaml`
```yaml
tiles:
  - [curve_left/W, straight/W, curve_left/N]
  - [straight/S, asphalt, straight/N]
  - [curve_left/S, straight/E, curve_left/E]

tile_size: 0.585

custom_textures:
  global:
    straight: "textures/night_road.png"
    curve_left: "textures/night_road.png"
    asphalt: "textures/night_asphalt.png"

objects:
  streetlight1:
    kind: tree  # Placeholder for streetlight
    pos: [1.5, 0.5]
    height: 0.3

  streetlight2:
    kind: tree
    pos: [1.5, 2.5]
    height: 0.3
```

**Load:**
```python
env = DuckietownEnv(
    map_name='night_track.yaml',
    domain_rand=False  # Disable randomization for consistent lighting
)
```

### Example 3: Training Curriculum

**Goal:** Generate progressively harder maps for RL training

```python
from gym_duckietown import MapBuilder

def create_training_map(difficulty):
    """Create map with difficulty-based complexity."""

    if difficulty == 'easy':
        # Small loop, no obstacles
        builder = MapBuilder.create_loop(size=3)

    elif difficulty == 'medium':
        # Larger loop, few obstacles
        builder = MapBuilder.create_loop(size=4)
        builder.add_object('duckie1', 'duckie', pos=[2.0, 2.0])
        builder.add_object('cone1', 'cone', pos=[2.0, 1.0])

    elif difficulty == 'hard':
        # Large loop, many obstacles
        builder = MapBuilder.create_loop(size=5)
        for i in range(5):
            builder.add_object(
                f'obstacle_{i}',
                'cone',
                pos=[1.5 + i*0.5, 2.5]
            )

    return builder.build()

# Training loop
for phase, difficulty in enumerate(['easy', 'medium', 'hard']):
    print(f"Training Phase {phase}: {difficulty}")
    map_data = create_training_map(difficulty)
    env = DuckietownEnv(map_data=map_data)

    # Train for N episodes
    for episode in range(100):
        obs = env.reset()
        # ... training code ...
```

### Example 4: A/B Testing Map Variations

**Goal:** Test different curve geometries for training

```python
from gym_duckietown import MapBuilder

# Variant A: Default curves
map_a = MapBuilder.create_loop(size=3).build()

# Variant B: Wide curves
builder_b = MapBuilder.create_loop(size=3)
# Add custom wide curves to all curve tiles
for i in [0, 2]:
    for j in [0, 2]:
        builder_b.set_custom_curves(i, j, [
            [[-0.15, 0, -0.50], [-0.15, 0, -0.10],
             [-0.10, 0, 0.15], [0.50, 0, 0.15]]
        ])
map_b = builder_b.build()

# Train on both and compare
for variant, map_data in [('A', map_a), ('B', map_b)]:
    env = DuckietownEnv(map_data=map_data)
    # ... evaluate performance ...
```

---

## Troubleshooting

### Textures Not Loading

**Symptom:**
```
WARNING:gym-duckietown:Custom texture not found: textures/road.png, using default
```

**Common Causes:**

1. **File doesn't exist**
   ```bash
   # Check file exists
   ls textures/road.png
   ```

2. **Wrong path (not relative to YAML)**
   ```yaml
   # WRONG (relative to current directory)
   custom_textures:
     global:
       straight: "road.png"

   # CORRECT (relative to YAML file)
   custom_textures:
     global:
       straight: "textures/road.png"
   ```

3. **Permission denied**
   ```bash
   # Fix permissions
   chmod 644 textures/road.png
   ```

4. **Invalid format**
   ```bash
   # Check file type
   file textures/road.png
   # Should say: PNG image data
   ```

**Solution Checklist:**
- [ ] File exists at specified path
- [ ] Path is relative to YAML file (or absolute)
- [ ] File is readable
- [ ] Format is PNG or JPG
- [ ] No typos in filename

### Curves Not Applied

**Symptom:**
```
○ Using default Bézier curves
```

**Common Causes:**

1. **Wrong tile key format**
   ```yaml
   # WRONG (spaces in key)
   custom_curves:
     "[0, 0]":

   # CORRECT (no spaces)
   custom_curves:
     "[0,0]":
   ```

2. **Wrong number of control points**
   ```yaml
   # WRONG (only 3 points)
   curves:
     - control_points:
       - [-0.2, 0, -0.5]
       - [-0.2, 0, 0.0]
       - [-0.2, 0, 0.5]

   # CORRECT (4 points)
   curves:
     - control_points:
       - [-0.2, 0, -0.5]
       - [-0.2, 0, -0.25]
       - [-0.2, 0, 0.25]
       - [-0.2, 0, 0.5]
   ```

3. **Missing Y coordinate**
   ```yaml
   # WRONG (2D coordinates)
   control_points:
     - [-0.2, -0.5]

   # CORRECT (3D with Y=0)
   control_points:
     - [-0.2, 0, -0.5]
   ```

**Debug:**
```python
env.reset()
tile = env.grid[0]
print("Custom curves loaded:", env.custom_curves_config is not None)
print("Tile curves:", tile.get('curves'))
```

### Map Not Found

**Symptom:**
```
KeyError: Could not find resource 'my_map.yaml'
```

**Solutions:**

```python
# Solution 1: Use absolute path
env = DuckietownEnv(map_name='/absolute/path/to/my_map.yaml')

# Solution 2: Register directory
import gym_duckietown
gym_duckietown.register_map_dir('./maps')
env = DuckietownEnv(map_name='my_map')  # No .yaml extension

# Solution 3: Check available maps
print(gym_duckietown.list_custom_maps())
```

### Validation Errors

**Symptom:**
```
ValueError: Map validation failed: Grid is not rectangular
```

**Cause:** Inconsistent row lengths

```yaml
# WRONG
tiles:
  - [straight/N, straight/N]        # 2 tiles
  - [straight/S, asphalt, straight/N]  # 3 tiles (inconsistent!)

# CORRECT (fill with 'empty' or 'asphalt')
tiles:
  - [straight/N, straight/N, asphalt]
  - [straight/S, asphalt, straight/N]
```

**MapBuilder:**
```python
# Validation happens automatically
builder = MapBuilder()
# ... forget to add tiles ...

map_data = builder.build()
# ValueError: Map validation failed: Map has no tiles
```

### Performance Issues

**Symptom:** Low FPS, slow loading

**Causes & Solutions:**

1. **Large textures**
   ```bash
   # Check texture size
   file textures/road.png
   # If > 2048×2048, resize:
   convert textures/road.png -resize 1024x1024 textures/road_small.png
   ```

2. **Too many objects**
   ```python
   # Limit objects per map
   if len(builder._objects) > 50:
       print("Warning: Many objects may impact performance")
   ```

3. **Complex curves**
   - Default curves are optimized
   - Custom curves computed per-reset (minimal impact)

---

## FAQ

### Can I create new tile types?

**No**, tile types are defined in duckietown-world package and include:
- `straight`, `curve_left`, `curve_right`
- `3way_left`, `3way_right`, `4way`
- `asphalt`, `grass`, `floor`, `empty`

**However**, you can use custom textures on existing tiles to make them look completely different!

### How do I debug my custom curves?

```python
# Method 1: Visual inspection (check robot stays on road)
env = DuckietownEnv(map_name='my_curves.yaml')
obs = env.reset()

# Method 2: Print curve data
tile = env.grid[0]
print(tile.get('curves'))

# Method 3: Plot curves (advanced)
import matplotlib.pyplot as plt
import numpy as np

curves = tile['curves']
for curve in curves:
    # curve shape: (4, 3) - 4 control points, 3D
    t = np.linspace(0, 1, 100)
    # Compute Bézier curve points...
    plt.plot(curve_points[:, 0], curve_points[:, 2])
plt.show()
```

### What texture formats are supported?

- **PNG** (recommended) - supports transparency
- **JPG/JPEG** - smaller files, no transparency

**Not supported:** BMP, GIF, TIFF, SVG

### How do I share custom maps?

**Method 1: Share directory**
```bash
# Package maps with textures
tar -czf my_maps.tar.gz maps/
# Share my_maps.tar.gz
```

**Method 2: Git repository**
```bash
git init my-duckietown-maps
cd my-duckietown-maps
# Add maps + textures
git add maps/ textures/
git commit -m "Add custom racing tracks"
git push
```

**Method 3: MapBuilder scripts**
```python
# Share Python script that generates map
# Recipients run script to create map_data
def create_my_map():
    return MapBuilder.create_loop(4).build()
```

### Can I mix YAML and MapBuilder?

**Yes!** Multiple ways:

**Method 1: Export MapBuilder to YAML**
```python
map_data = MapBuilder.create_loop(4).build()
MapBuilder.save_yaml(map_data, 'generated.yaml')

# Later, load as YAML
env = DuckietownEnv(map_name='generated.yaml')
```

**Method 2: Load YAML, modify in Python**
```python
import yaml

# Load existing YAML
with open('base_map.yaml') as f:
    map_data = yaml.load(f, Loader=yaml.Loader)

# Modify programmatically
map_data['objects']['new_duckie'] = {
    'kind': 'duckie',
    'pos': [2.0, 2.0]
}

# Use directly
env = DuckietownEnv(map_data=map_data)
```

### Do custom features work with domain randomization?

**Yes!** Domain randomization is independent:

```python
env = DuckietownEnv(
    map_name='my_custom_map.yaml',
    domain_rand=True  # Randomizes lighting, dynamics, etc.
)
```

Custom textures and curves are preserved while other aspects randomize.

### How do I contribute custom maps to the project?

1. Create your custom map (with examples/documentation)
2. Test thoroughly
3. Submit PR to gym-duckietown repository
4. Include:
   - Map YAML file
   - Texture files (if used)
   - README describing the map
   - Screenshots/videos

---

## Quick Reference

### Load Custom Map

```python
from gym_duckietown.envs import DuckietownEnv

# By file path
env = DuckietownEnv(map_name='/path/to/map.yaml')

# By name (after registration)
import gym_duckietown
gym_duckietown.register_map_dir('./maps')
env = DuckietownEnv(map_name='my_map')

# With map_data (MapBuilder)
from gym_duckietown import MapBuilder
map_data = MapBuilder.create_loop(4).build()
env = DuckietownEnv(map_data=map_data)

# With map_dirs parameter
env = DuckietownEnv(
    map_name='my_map',
    map_dirs=['./my_maps', './backup_maps']
)
```

### Custom Textures YAML

```yaml
custom_textures:
  # Global (all tiles of this type)
  global:
    straight: "textures/road.png"
    curve_left: "textures/curve.png"

  # Tile-specific (individual tiles)
  tile_overrides:
    "[0,0]": "textures/start.png"
    "[2,3]": "textures/special.png"
```

### Custom Curves YAML

```yaml
custom_curves:
  "[i,j]":  # Tile position
    type: "bezier"
    curves:
      # Lane 1 (4 control points each)
      - control_points:
        - [x1, 0, z1]  # Start
        - [x2, 0, z2]  # Control 1
        - [x3, 0, z3]  # Control 2
        - [x4, 0, z4]  # End

      # Lane 2
      - control_points:
        - [x1, 0, z1]
        - [x2, 0, z2]
        - [x3, 0, z3]
        - [x4, 0, z4]
```

### MapBuilder API

```python
from gym_duckietown import MapBuilder

# Template (quick start)
map_data = MapBuilder.create_loop(size=4).build()
map_data = MapBuilder.create_straight_road(length=10, orientation='N').build()

# Custom (fluent API)
map_data = (MapBuilder()
    .add_tile(0, 0, 'straight', 'N')
    .add_tile(1, 0, 'curve_left', 'N')
    .add_object('duckie1', 'duckie', pos=[1.5, 1.5])
    .set_start_tile((0, 0))
    .set_global_texture('straight', 'textures/road.png')
    .set_custom_curves(0, 0, [[control_points]])
    .build())

# Export to YAML
MapBuilder.save_yaml(map_data, 'output.yaml')

# Validation
is_valid, errors = builder.validate()
```

### MapRegistry API

```python
import gym_duckietown

# Register directories
gym_duckietown.register_map_dir('./maps')
gym_duckietown.register_map_dir('/shared/team_maps')

# List registered directories
dirs = gym_duckietown.list_map_dirs()

# List discovered maps
maps = gym_duckietown.list_custom_maps()

# Resolve name to path
path = gym_duckietown.resolve_map('my_custom_map')

# Clear all
gym_duckietown.clear_map_registry()
```

### Tile Types

- `straight` - Straight road
- `curve_left` - Left turn
- `curve_right` - Right turn
- `3way_left` - T-intersection (left branch)
- `3way_right` - T-intersection (right branch)
- `4way` - 4-way intersection
- `asphalt` - Plain asphalt (no markings)
- `grass` - Grass tile
- `floor` - Indoor floor
- `empty` - Empty space

### Orientations

- `N` - North (up, 0°)
- `E` - East (right, 90°)
- `S` - South (down, 180°)
- `W` - West (left, 270°)

### Object Types

- `duckie` - Yellow duck
- `duckiebot` - Robot duck
- `cone` - Traffic cone
- `barrier` - Jersey barrier
- `tree` - Tree
- `house` - Building
- `sign_stop` - Stop sign
- `sign_left_T_intersect` - Left T-intersection sign
- `sign_right_T_intersect` - Right T-intersection sign
- `sign_4_way_intersect` - 4-way intersection sign
- More in duckietown-world package

---

## Additional Resources

- **Demo Script**: `python demo_custom_maps.py` - Interactive demo with 5 example maps
- **Examples Directory**: `examples/custom_maps/` - 6 working example maps with textures
- **API Documentation**: See `API_REFERENCE.md` for complete API details
- **Duckietown Docs**: https://docs.duckietown.org/
- **GitHub Issues**: https://github.com/duckietown/gym-duckietown/issues

---

**Happy custom world building! 🦆🏁**
