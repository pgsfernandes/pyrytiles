import os
import struct
from PIL import Image, ImageOps
from pathlib import Path
import numpy as np

TILE_SIZE = 8
METATILE_SIZE = 16

def load_palette_images(path, count):
    palette_images = []
    for i in range(count):
        img_path = os.path.join(path, f"tiles_palette_{i}.png")
        if os.path.exists(img_path):
            palette_images.append(Image.open(img_path).convert("P"))
        else:
            print(f"Warning: Palette image {img_path} not found.")
    return palette_images

def apply_gba_quantization(img):
    """
    Takes a PIL Image (RGBA) and returns a new image
    with GBA-style color quantization applied.
    """
    img = img.convert("RGBA")  # ensure correct mode
    
    def to_gba(c):
        r, g, b, a = c
        return ((r // 8) * 8,
                (g // 8) * 8,
                (b // 8) * 8,
                a)

    pixels = list(img.getdata())
    gba_pixels = [to_gba(p) for p in pixels]

    new_img = Image.new("RGBA", img.size)
    new_img.putdata(gba_pixels)
    
    return new_img
'''
def compute_palette_per_tile(tiles_img, palette_images):
    w, h = tiles_img.size
    tiles_x = w // TILE_SIZE
    tiles_y = h // TILE_SIZE
    result = []
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            best_palette, best_score = 0, float("inf")
            for p_idx, pal_img in enumerate(palette_images):
                score = 0
                for y in range(TILE_SIZE):
                    for x in range(TILE_SIZE):
                        rgba = tiles_img.getpixel((tx * TILE_SIZE + x, ty * TILE_SIZE + y))
                        if rgba[3] < 128: continue 
                        pal_pixel_idx = pal_img.getpixel((tx * TILE_SIZE + x, ty * TILE_SIZE + y))
                        if pal_pixel_idx == 0: continue
                        palette_data = pal_img.getpalette()
                        pr, pg, pb = palette_data[pal_pixel_idx*3 : pal_pixel_idx*3 + 3]
                        score += (rgba[0] - pr)**2 + (rgba[1] - pg)**2 + (rgba[2] - pb)**2
                if score < best_score:
                    best_score, best_palette = score, p_idx
            result.append(best_palette)
    return result
'''
'''
def compute_palette_per_tile(
    tiles_path: str,
    palette_folder: str,
    tile_size: int = 8,
    num_palettes: int = 6,
) -> list[int]:
    """
    For each 8x8 tile in tiles_path, find which palette image (0..num_palettes-1)
    has the closest matching color for that tile.

    Args:
        tiles_path:      Path to the reference tiles image.
        palette_folder:  Folder containing tiles_palette_0.png … tiles_palette_N.png
        tile_size:       Size of each square tile in pixels (default 8).
        num_palettes:    Number of palette images (default 5).

    Returns:
        A flat list of ints, one per tile (row-major order), giving the index
        of the palette whose tile color best matches the reference.
    """
    ref = np.array(Image.open(tiles_path).convert("RGB"), dtype=np.int32)
    h, w = ref.shape[:2]

    tiles_y = h // tile_size
    tiles_x = w // tile_size
    num_tiles = tiles_y * tiles_x

    folder = Path(palette_folder)
    palettes = [
        np.array(
            Image.open(folder / f"tiles_palette_{i}.png").convert("RGB"),
            dtype=np.int32,
        )
        for i in range(num_palettes)
    ]

    # Shape: (num_palettes, num_tiles) — MSE of each palette tile vs reference tile
    errors = np.zeros((num_palettes, num_tiles), dtype=np.float64)

    tile_idx = 0
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            y0, y1 = ty * tile_size, (ty + 1) * tile_size
            x0, x1 = tx * tile_size, (tx + 1) * tile_size

            ref_tile = ref[y0:y1, x0:x1]  # (tile_size, tile_size, 3)

            for p, pal in enumerate(palettes):
                diff = pal[y0:y1, x0:x1] - ref_tile
                errors[p, tile_idx] = np.mean(diff ** 2)

            tile_idx += 1

    # For each tile pick the palette with the lowest MSE
    best_palette = np.argmin(errors, axis=0).tolist()
    return best_palette
'''

import numpy as np
from PIL import Image
from pathlib import Path


def load_jasc_pal(filepath):
    with open(filepath, "r") as f:
        lines = [line.strip() for line in f.readlines()]

    if lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError(f"{filepath} is not a valid JASC-PAL file")

    count = int(lines[2])
    colors = [tuple(map(int, line.split())) for line in lines[3:3 + count]]
    return np.array(colors, dtype=np.int32)  # (num_colors, 3)
'''
def compute_palette_per_tile(
    tiles_path: str,
    palette_folder: str,
    tile_size: int = 8,
    num_palettes: int = 6,
) -> list[int]:
    """
    Same idea as original, but uses JASC-PAL files instead of palette images.
    """

    ref = np.array(Image.open(tiles_path).convert("RGB"), dtype=np.int32)
    h, w = ref.shape[:2]

    tiles_y = h // tile_size
    tiles_x = w // tile_size
    num_tiles = tiles_y * tiles_x

    folder = Path(palette_folder)

    # Load .pal files
    palettes = [
        load_jasc_pal(folder / f"0{i}.pal")
        for i in range(num_palettes)
    ]
    # Each palette: (num_colors, 3)

    errors = np.zeros((num_palettes, num_tiles), dtype=np.float64)

    tile_idx = 0
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            y0, y1 = ty * tile_size, (ty + 1) * tile_size
            x0, x1 = tx * tile_size, (tx + 1) * tile_size

            ref_tile = ref[y0:y1, x0:x1].reshape(-1, 3)  # (N, 3)

            for p, pal in enumerate(palettes):
                # Compute distance from each pixel to each palette color
                # shape: (num_pixels, num_colors)
                diff = ref_tile[:, None, :] - pal[None, :, :]
                dist2 = np.sum(diff ** 2, axis=2)

                # For each pixel, take closest palette color
                min_dist2 = np.min(dist2, axis=1)

                # Mean squared error for tile
                errors[p, tile_idx] = np.mean(min_dist2)

            tile_idx += 1

    best_palette = np.argmin(errors, axis=0).tolist()
    return best_palette
'''
def to_gba_np(arr):
    """Vectorized GBA color quantization for numpy arrays."""
    # (arr // 8) * 8 clears the lower 3 bits, matching your function logic
    return (arr // 8) * 8

def compute_palette_per_tile(
    tiles_path: str,
    palette_folder: str,
    tile_size: int = 8,
    num_palettes: int = 6,
) -> list[int]:
    
    # 1. Load and immediately quantize the source image
    raw_img = np.array(Image.open(tiles_path).convert("RGB"), dtype=np.uint8)
    img = to_gba_np(raw_img)
    
    h, w = img.shape[:2]
    tiles_y, tiles_x = h // tile_size, w // tile_size
    folder = Path(palette_folder)

    # 2. Load and quantize palettes
    palette_sets = []
    for i in range(num_palettes):
        pal_path = folder / f"{i:02d}.pal"
        # Quantize the palette colors so they match the quantized image colors
        pal = load_jasc_pal(pal_path).astype(np.uint8)
        quantized_pal = to_gba_np(pal)
        
        palette_sets.append(set(map(tuple, quantized_pal)))

    results = []

    # 3. Process tiles
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            y0, x0 = ty * tile_size, tx * tile_size
            tile = img[y0 : y0 + tile_size, x0 : x0 + tile_size]

            # Get unique quantized colors
            unique_colors_np = np.unique(tile.reshape(-1, 3), axis=0)
            unique_colors_set = set(map(tuple, unique_colors_np))

            match_index = -1 
            for i, pset in enumerate(palette_sets):
                if unique_colors_set.issubset(pset):
                    match_index = i
                    break

            results.append(match_index)
    print(results)
    return results

def get_tile_lookup(unique_img, palette_list):
    lookup = {}
    
    # Calculate grid dimensions
    tiles_wide = unique_img.width // TILE_SIZE  # e.g., 128 // 8 = 16
    tiles_high = unique_img.height // TILE_SIZE # e.g., 256 // 8 = 32
    
    # Total number of 8x8 tiles in the unique_tiles image
    num_tiles = tiles_wide * tiles_high
    print(f"Indexing {num_tiles} unique tiles ({tiles_wide}x{tiles_high} grid)...")

    for i in range(num_tiles):
        # Calculate the X and Y coordinate of the tile in the unique_tiles grid
        # i % 16 gives the column (0-15)
        # i // 16 gives the row (0-31)
        tx = (i % tiles_wide) * TILE_SIZE
        ty = (i // tiles_wide) * TILE_SIZE
        
        # Crop the 8x8 area
        base_tile = unique_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
        
        # Ensure we don't go out of range of the palette list
        pal_id = palette_list[i] if i < len(palette_list) else 0
        
        # Generate all 4 orientation variants for this specific tile
        for h_flip in [0, 1]:
            for v_flip in [0, 1]:
                t = base_tile
                if h_flip: t = ImageOps.mirror(t)
                if v_flip: t = ImageOps.flip(t)
                
                pixels = tuple(t.getdata())
                # If this specific visual pattern hasn't been seen yet, 
                # map it back to the original tile index (i) and the required flips
                if pixels not in lookup:
                    lookup[pixels] = (i, pal_id, h_flip, v_flip)
                    
    return lookup

def is_metatile_empty(img, x, y):
    """Checks if a 16x16 area is entirely Magenta (255, 0, 255)."""
    #MAGENTA = (255, 0, 255)
    MAGENTA = (248, 0, 248)
    # Convert crop to RGB and get data to check pixels
    patch = img.crop((x, y, x + 16, y + 16)).convert("RGB")
    pixels = list(patch.getdata())
    return all(p == MAGENTA for p in pixels)

def build_metatiles_bin(bottom_path, middle_path, top_path, unique_path, palette_folder, output_path):
    # Load and prep images
    bottom_img = Image.open(bottom_path).convert("RGBA")
    mid_img = Image.open(middle_path).convert("RGBA")
    top_img = Image.open(top_path).convert("RGBA")
    unique_img = Image.open(unique_path).convert("RGBA")
    
    pal_imgs = load_palette_images(palette_folder, 6)
    #palette_list = compute_palette_per_tile(unique_img, pal_imgs)
    palette_list = compute_palette_per_tile(unique_path, palette_folder)
    tile_lookup = get_tile_lookup(unique_img, palette_list)
    
    bin_data = bytearray()

    def get_tile_value(img, tx, ty):
        quad = img.crop((tx, ty, tx + 8, ty + 8))
        pix = tuple(quad.getdata())

        # Check if tile is completely transparent
        #if all(p[3] < 10 for p in pix):
        #    return 0

        if pix in tile_lookup:
            # 'idx' here is the index in your unique_tiles.png
            idx, pal, h, v = tile_lookup[pix]
            
            # Return the 16-bit GBA value
            return (pal << 12) | (v << 11) | (h << 10) | (idx & 0x3FF)
        
        return 0

    print("Encoding metatiles...")
    for y in range(0, bottom_img.height, METATILE_SIZE):
        for x in range(0, bottom_img.width, METATILE_SIZE):
            if is_metatile_empty(bottom_img,x,y):
                # 1. LAYER 1 (Middle) - 4 tiles
                for ty in [0, 8]:
                    for tx in [0, 8]:
                        val = get_tile_value(mid_img, x + tx, y + ty)
                        bin_data.extend(struct.pack('<H', val))
                
                # 2. LAYER 2 (Upper/Top) - 4 tiles
                for ty in [0, 8]:
                    for tx in [0, 8]:
                        val = get_tile_value(top_img, x + tx, y + ty)
                        bin_data.extend(struct.pack('<H', val))
            elif is_metatile_empty(mid_img,x,y):
                # 1. LAYER 1 (Middle) - 4 tiles
                for ty in [0, 8]:
                    for tx in [0, 8]:
                        val = get_tile_value(bottom_img, x + tx, y + ty)
                        bin_data.extend(struct.pack('<H', val))
                
                # 2. LAYER 2 (Upper/Top) - 4 tiles
                for ty in [0, 8]:
                    for tx in [0, 8]:
                        val = get_tile_value(top_img, x + tx, y + ty)
                        bin_data.extend(struct.pack('<H', val))
            else:
                # 1. LAYER 1 (Middle) - 4 tiles
                for ty in [0, 8]:
                    for tx in [0, 8]:
                        val = get_tile_value(bottom_img, x + tx, y + ty)
                        bin_data.extend(struct.pack('<H', val))
                
                # 2. LAYER 2 (Upper/Top) - 4 tiles
                for ty in [0, 8]:
                    for tx in [0, 8]:
                        val = get_tile_value(mid_img, x + tx, y + ty)
                        bin_data.extend(struct.pack('<H', val))
            '''
            # 1. LAYER 1 (Bottom) - 4 tiles
            for ty in [0, 8]:
                for tx in [0, 8]:
                    val = get_tile_value(bottom_img, x + tx, y + ty)
                    bin_data.extend(struct.pack('<H', val))
            
            # 2. LAYER 2 (Upper/Top) - 4 tiles
            for ty in [0, 8]:
                for tx in [0, 8]:
                    val = get_tile_value(top_img, x + tx, y + ty)
                    bin_data.extend(struct.pack('<H', val))
            '''

    with open(output_path, "wb") as f:
        f.write(bin_data)
    print(f"Success! {output_path} generated.")

if __name__ == "__main__":
    build_metatiles_bin(
        bottom_path="emerald/bottom.png",
        middle_path="emerald/middle.png",
        top_path="emerald/top.png",
        unique_path="emerald_out/unique_tiles.png",
        palette_folder="emerald_out",
        output_path="emerald_out/metatiles.bin"
    )