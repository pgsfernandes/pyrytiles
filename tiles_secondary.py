import os
import glob
from PIL import Image

from PIL import Image, ImageOps
import sys
from config import TILE_SIZE

OUTPUT_WIDTH = 128
OUTPUT_HEIGHT = 256

def split_into_tiles(img):
    tiles = []
    for y in range(0, img.height, TILE_SIZE):
        for x in range(0, img.width, TILE_SIZE):
            tile = img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
            tiles.append(tile)
    return tiles

def get_tile_variants(tile):
    return [
        tile,
        ImageOps.mirror(tile),  # horizontal
        ImageOps.flip(tile),    # vertical
        ImageOps.flip(ImageOps.mirror(tile))  # both
    ]

def canonical_tile_key(tile):
    return min(v.tobytes() for v in get_tile_variants(tile))

def create_magenta_tile():
    # Create a solid magenta (255, 0, 255) tile
    return Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (255, 0, 255, 255))

def collect_unique_tiles(all_tiles):
    seen = set()
    unique_tiles = []
    
    # 1. Prepare the mandatory magenta tile and its key
    #magenta_tile = create_magenta_tile()
    #magenta_key = canonical_tile_key(magenta_tile)
    
    # Pre-populate seen with the magenta key so we don't add it again later
    #seen.add(magenta_key)
    #unique_tiles.append(magenta_tile)

    for tile in all_tiles:
        key = canonical_tile_key(tile)
        if key not in seen:
            seen.add(key)
            unique_tiles.append(tile)
        # Note: If a magenta tile was in all_tiles, 'seen.add' above 
        # ensures it is skipped during the loop, keeping our index 0 version.

    return unique_tiles

def create_output_image(unique_tiles):
    tiles_per_row = OUTPUT_WIDTH // TILE_SIZE  # 16
    tiles_per_col = OUTPUT_HEIGHT // TILE_SIZE  # 32
    max_tiles = tiles_per_row * tiles_per_col  # 512

    if len(unique_tiles) > max_tiles:
        raise ValueError(f"Too many unique tiles: {len(unique_tiles)} (max {max_tiles})")

    output_img = Image.new("RGBA", (OUTPUT_WIDTH, OUTPUT_HEIGHT))

    for idx, tile in enumerate(unique_tiles):
        x = (idx % tiles_per_row) * TILE_SIZE
        y = (idx // tiles_per_row) * TILE_SIZE
        output_img.paste(tile, (x, y))

    return output_img

def load_and_validate(path):
    img = Image.open(path).convert("RGBA")

    if img.width % TILE_SIZE != 0 or img.height % TILE_SIZE != 0:
        raise ValueError(f"{path}: dimensions must be multiples of 8")

    return img

def dedup(input_paths, output_path=None, save=True, verbose=True):
    all_tiles = []

    for path in input_paths:
        img = load_and_validate(path)
        tiles = split_into_tiles(img)
        all_tiles.extend(tiles)

    unique_tiles = collect_unique_tiles(all_tiles)
    
    print(f"Unique tiles (with reflections): {len(unique_tiles)}")

    output_img = create_output_image(unique_tiles)

    if save and output_path:
        output_img.save(output_path)
        if verbose:
            print(f"Saved output to {output_path}")

    return output_img, unique_tiles

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

            if 0 <= pal_id <= 5:   # ← filter here
                pals[pal_id] = load_jasc_pal_as_list(pf)

        except ValueError:
            continue
    return pals

def create_tileset_library(tiles_png_path, palettes):
    if not os.path.exists(tiles_png_path):
        return {}

    base_img = Image.open(tiles_png_path).convert("P")
    library = {}

    for pal_id, pal_data in palettes.items():
        version = base_img.copy()
        version.putpalette(pal_data)
        rgba = version.convert("RGBA")
        new_pixels = [
			#(r, g, b, 255) if idx == 0 else (r, g, b, a)
			(r, g, b, a)
			for idx, (r, g, b, a) in zip(base_img.getdata(), rgba.getdata())
		]

        rgba.putdata(new_pixels)
        library[pal_id] = rgba

    return library

from config import TILE_SIZE, MAGENTA

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
            # Apply GBA color conversion to secondary layers
            secondary_tiles_raw.extend(split_into_tiles(img))

    # 3. FILTER & DEDUPLICATE
    # Now both sets are in GBA color space, so comparisons are accurate
    filtered_secondary = [
        tile for tile in secondary_tiles_raw 
        if canonical_tile_key(tile) not in primary_canonical_keys
    ]

    # Collect unique tiles (handles Magenta tile at index 0)
    unique_secondary_tiles = collect_unique_tiles(filtered_secondary)
    
    print(f"Primary variants indexed: {len(primary_canonical_keys)}")
    print(f"New secondary tiles added: {len(unique_secondary_tiles)}")

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
    output_img.save(os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/debug.png"))

    return output_img, tile_color_sets, palettes

#input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompiletest3")
#input_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompiletestsec/output2")
#input_dir_secondary = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/decompiletest3/output2")
#load_tiles_sec(input_dir_secondary,input_dir)