# pyrytiles - A pokeemerald Tileset Compiler & Decompiler

A Python-based tool, inspired by [Porytiles](https://github.com/grunt-lucas/porytiles), for compiling and decompiling tilesets in `pokeemerald` decomp projects.

## Features

- **Compile Primary Tilesets**: Build primary tilesets from image layers (`bottom.png`, `middle.png` and `top.png`) and a CSV with metatile attributes (`attributes.csv`).
- **Compile Secondary Tileset**: Build secondary tilesets. Secondary tilesets can be paired with a primary tileset to efficiently reuse palettes and tiles.
- **Decompile**: Convert binary `metatiles.bin` and `metatile_attributes.bin`, together with a `tiles.png` image back into editable PNG layers (`bottom.png`, `middle.png`, `top.png`) and an `attributes.csv`.
- **Triple-Layer Support**: Choose between dual-layer or triple-layer metatiles.
- **CP-SAT solver**: Uses a [CP-SAT solver](https://developers.google.com/optimization/cp/cp_solver) which efficiently finds a suitable combination of palettes if mathematically possible, otherwise proves that it is not.
- **Finding an optimal solution**: Option to find the solution that minimizes the number of palettes used. For example, with this option set to True, the primary tileset of Pokémon Emerald can be compiled with only 5 palettes (instead of 6), and a couple of unused slots in the remaining palettes.

Ensure you have [Python 3.x](https://www.python.org/) installed, along with all necessary libraries.

## Usage

Operations are controlled via a python file such as `main.py`.

### 1. Compiling a Primary Tileset

```python
from compilers import compile_primary

compile_primary(
    path="Path/To/Layer/Images",
    out_dir="Path/To/Project/data/tilesets/primary/tileset_name",
    optimal = False, # If True, tries to find the optimal combination of palettes that minimizes the number of palettes used. Takes longer, and for most cases, a working solution is enough.
    triple_layer=False # Set to True if using triple-layer metatiles
)
```

### 2. Compiling a Secondary Tileset

```python
from compilers import compile_secondary

compile_secondary(
    path="Path/To/Layer/Images",
    out_dir="Path/To/Project/data/tilesets/secondary/secondary_tileset_name",
    path_primary="Path/To/Project/data/tilesets/primary/primary_tileset_name", #If paired with a primary tileset, otherwise leave blank
    optimal = False, # If True, tries to find the optimal combination of palettes that minimizes the number of palettes used. Takes longer, and for most cases, a working solution is enough.
    triple_layer=False # Set to True if using triple-layer metatiles
)
```

### 3. Decompiling a Tileset

```python
from decompile import decompile_tileset

# Decompile a Primary Tileset
decompile_tileset(
    primary_path="data/tilesets/primary/tileset_name", 
    out_dir="Path/To/Folder/tileset_name_decompiled",
    triple_layer=False # Set to True if primary tileset was compiled using triple-layer metatiles
)

# Decompile a Secondary Tileset
decompile_tileset(
    primary_path="data/tilesets/primary/primary_tileset_name",
    secondary_path="data/tilesets/secondary/secondary_tileset_name", 
    out_dir="Path/To/Folder/tileset_name_decompiled",
    triple_layer=False # Set to True if the primary and secondary tilesets were compiled using triple-layer metatiles
)
```