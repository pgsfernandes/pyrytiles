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
    magenta_tile = create_magenta_tile()
    magenta_key = canonical_tile_key(magenta_tile)
    
    # Pre-populate seen with the magenta key so we don't add it again later
    seen.add(magenta_key)
    unique_tiles.append(magenta_tile)

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

def dedup_from_imgs(imgs):
    all_tiles = []

    for img in imgs:
        tiles = split_into_tiles(img)
        all_tiles.extend(tiles)

    unique_tiles = collect_unique_tiles(all_tiles)

    output_img = create_output_image(unique_tiles)

    return output_img, unique_tiles