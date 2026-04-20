import os
import glob
from config import TILE_SIZE, MAGENTA, NUM_PALETTES
import numpy as np
from tiles_dedup import split_into_tiles, canonical_tile_key, create_output_image, load_and_validate
from utils import create_tileset_library

def collect_unique_tiles(all_tiles):
    seen = set()
    unique_tiles = []

    for tile in all_tiles:
        key = canonical_tile_key(tile)
        if key not in seen:
            seen.add(key)
            unique_tiles.append(tile)

    return unique_tiles

def load_jasc_pal_as_list(filepath):
    colors = []
    with open(filepath, 'r') as f:
        # Skip the JASC-PAL header (3 lines)
        lines = f.readlines()[3:]
        
        for i, line in enumerate(lines):
            parts = line.split()
            if len(parts) >= 3:
                if i == 0:
                    # FORCE the first color to GBA-compatible Magenta
                    colors.extend([255, 0, 255])
                else:
                    # Load all other colors as they are
                    colors.extend([int(parts[0]), int(parts[1]), int(parts[2])])
                    
    # Ensure the palette list is exactly 768 entries (256 colors * 3 channels)
    # for PIL's 'P' mode requirement.
    while len(colors) < 768:
        colors.extend([255, 0, 255])
        
    return colors[:768]

def load_palettes(path):
    pals = {}
    for pf in glob.glob(os.path.join(path, "palettes", "*.pal")):
        try:
            pal_id = int(os.path.basename(pf).split('.')[0])

            if 0 <= pal_id <= NUM_PALETTES-1:   # ← filter here
                pals[pal_id] = load_jasc_pal_as_list(pf)

        except ValueError:
            continue
    return pals

def load_tiles_sec(secondary_path,primary_path):
    # 1. LOAD AND NORMALIZE PRIMARY DATA
    palettes = load_palettes(primary_path)
    tiles_png_path = os.path.join(primary_path, "tiles.png")
    
    # Create the library with recolored palettes
    primary_library = create_tileset_library(tiles_png_path, palettes)
    
    primary_canonical_keys = set()
    for pal_id, full_image in primary_library.items():
        recolored_tiles = split_into_tiles(full_image)
        
        for tile in recolored_tiles:
            primary_canonical_keys.add(canonical_tile_key(tile))

    # 2. LOAD AND NORMALIZE SECONDARY DATA
    layer_names = ["bottom", "middle", "top"]
    secondary_tiles_raw = []
    
    for name in layer_names:
        p = os.path.join(secondary_path, f"{name}.png")
        if os.path.exists(p):
            img = load_and_validate(p)
            secondary_tiles_raw.extend(split_into_tiles(img))

    def is_uniform(tile):
        """Returns True if all pixels in the tile are the same color."""
        # Convert PIL Image to NumPy array if it hasn't been converted yet
        tile_data = np.asarray(tile)
        
        # Check if all pixels match the top-left pixel
        # tile_data[0, 0] is the RGB value of the first pixel
        return np.all(tile_data == tile_data[0, 0])

    # 3. FILTER & DEDUPLICATE
    filtered_secondary = []
    for tile in secondary_tiles_raw:
        # Condition 1: Tile is not in the primary tileset
        not_in_primary = canonical_tile_key(tile) not in primary_canonical_keys
        
        # Condition 2: Tile has no structure (all same color)
        is_solid_color = is_uniform(tile)
        
        if not_in_primary or is_solid_color:
            filtered_secondary.append(tile)

    # Collect unique tiles (handles Magenta tile at index 0)
    unique_secondary_tiles = collect_unique_tiles(filtered_secondary)
    
    print(f"Number of unique secondary-exclusive tiles: {len(unique_secondary_tiles)}")

    # 4. GENERATE OUTPUT
    output_img = create_output_image(unique_secondary_tiles)
    
    # Final color set list for metadata
    tile_color_sets = []
    for tile in unique_secondary_tiles:
        colors = {
            tile.getpixel((x, y))[:3]
            for y in range(TILE_SIZE)
            for x in range(TILE_SIZE)
            if tile.getpixel((x, y))[3] != 0
        }
        # Ensure Magenta (GBA version) is removed from the set
        colors.discard(MAGENTA)
        tile_color_sets.append(colors)

    return output_img, tile_color_sets