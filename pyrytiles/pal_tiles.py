import os
from PIL import Image
import numpy as np
from collections import defaultdict
from .utils import nearest_palette_index
from .config import *

# ========================
# PALETTE BUILDING
# ========================
'''
def build_palettes(tiles, assignment):
    palettes = defaultdict(set)

    for tile, p in zip(tiles, assignment):
        palettes[p] |= tile

    final = []

    for p in range(NUM_PALETTES):
        colors = [c for c in list(palettes[p])[:MAX_COLORS]]

        palette = [MAGENTA] + colors
        palette += [(0, 0, 0)] * (16 - len(palette))

        final.append(palette)

    return final
'''

def build_palettes(tiles, assignment, is_secondary=False):
    palettes = defaultdict(set)
    for tile, p in zip(tiles, assignment):
        # If is_secondary is True, skip entries where p < NUM_PALETTES
        if is_secondary and p < NUM_PALETTES:
            continue

        if is_secondary:   
            palettes[p-NUM_PALETTES] |= tile
        else:
            palettes[p] |= tile

    final = []

    for p in range(NUM_PALETTES):
        # Note: If is_secondary is True, palettes[p] will be empty for p < NUM_PALETTES
        colors = [c for c in list(palettes[p])[:MAX_COLORS]]

        palette = [MAGENTA] + colors
        palette += [(0, 0, 0)] * (16 - len(palette))

        final.append(palette)

    return final


# ========================
# EXPORT PALETTE
# ========================
def export_jasc(palettes, out_dir, is_primary=True):
    os.makedirs(out_dir, exist_ok=True)

    def write_pal(path, pal):
        with open(path, "w") as f:
            f.write("JASC-PAL\n0100\n16\n")
            for r, g, b in pal:
                f.write(f"{r} {g} {b}\n")

    # Define special palettes
    empty_pal = [(0, 0, 0)] * 16
    primary_marked_pal = [(255, 0, 255)] + [(0, 0, 0)] * 15

    if is_primary:
        for i in range(13):
            filename = f"{i:02d}.pal"
            path = os.path.join(out_dir, filename)

            if 6 <= i <= 11:
                write_pal(path, primary_marked_pal)
            elif i==12:
                write_pal(path, empty_pal)
            else:
                write_pal(path, palettes[i])
    else:
        for i in range(13):
            filename = f"{i:02d}.pal"
            path = os.path.join(out_dir, filename)

            if 0 <= i <= 5 or i==12:
                write_pal(path, empty_pal)
            else:
                write_pal(path, palettes[i - 6])

    print("Palettes exported")
'''

# ========================
# IMAGE EXPORT
# ========================
def build_pil_palette(palette):
    flat = [v for color in palette for v in color]
    flat += [0] * (256 * 3 - len(flat))
    return flat

def make_grayscale_palette() -> list:
    """
    Returns a 16-color palette with magenta as the first color,
    followed by 15 evenly spaced grayscale colors.
    """
    palette = [(255, 0, 255)]
    for i in range(15):
        v = round(i * 255 / 14)
        palette.append((v, v, v))
    return palette


def export_indexed_image(img, assignment, palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    w, h = img.size
    tiles_x = w // TILE_SIZE

    composite = Image.new("P", (w, h))
    composite.putpalette(build_pil_palette(make_grayscale_palette()))

    for i, assigned_p in enumerate(assignment):
        palette = palettes[assigned_p]

        tx = (i % tiles_x) * TILE_SIZE
        ty = (i // tiles_x) * TILE_SIZE

        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                raw = img.getpixel((tx + x, ty + y))

                idx = 0 if raw == MAGENTA else nearest_palette_index(raw, palette)
                composite.putpixel((tx + x, ty + y), idx)

    composite.save(os.path.join(out_dir, "tiles.png"), bits=4)
'''

# ========================
# FOR ANIMATIONS
# ========================
'''
def index_image_from_master(target_img, master_indexed_img):
    """
    target_img: The new RGB/RGBA image you want to index.
    master_indexed_img: The 8-bit indexed 'P' mode image (your source of truth).
    """
    # 1. Convert everything to numpy arrays for fast comparison
    # We convert target to RGB to ensure we are comparing colors, not alpha/metadata
    target_arr = np.array(target_img.convert("RGB"))
    
    # Master RGB is used for color matching
    master_rgb = np.array(master_indexed_img.convert("RGB"))
    # Master Indices contains the 0-95 values we want to steal
    master_indices = np.array(master_indexed_img)

    tw, th, _ = target_arr.shape
    mw, mh, _ = master_rgb.shape

    # 2. Extract all unique 8x8 tiles from the Master for a lookup table
    # Key: Tile as a byte-string (for hashability), Value: The 8x8 index grid
    tile_lookup = {}
    for y in range(0, mw, 8):
        for x in range(0, mh, 8):
            rgb_tile = master_rgb[y:y+8, x:x+8]
            idx_tile = master_indices[y:y+8, x:x+8]
            
            # Use tobytes() so the array can be used as a dictionary key
            tile_key = rgb_tile.tobytes()
            if tile_key not in tile_lookup:
                tile_lookup[tile_key] = idx_tile

    # 3. Build the new indexed image
    new_indices = np.zeros((tw, th), dtype=np.uint8)

    for y in range(0, tw, 8):
        for x in range(0, th, 8):
            target_tile = target_arr[y:y+8, x:x+8]
            target_key = target_tile.tobytes()

            if target_key in tile_lookup:
                # Copy the indices (0-95) from the master
                new_indices[y:y+8, x:x+8] = tile_lookup[target_key]
            else:
                # Handle tiles not found in master (default to 0/Magenta)
                print(f"Warning: Tile at {x},{y} not found in master tileset.")
                new_indices[y:y+8, x:x+8] = 0

    # 4. Convert back to PIL Image and apply the master palette
    result_img = Image.fromarray(new_indices, mode="P")
    result_img.putpalette(master_indexed_img.getpalette())
    
    return result_img
'''
def index_image_from_master(target_img, master_indexed_img):
    target_arr = np.array(target_img.convert("RGB"))
    master_rgb = np.array(master_indexed_img.convert("RGB"))
    master_indices = np.array(master_indexed_img)

    tw, th, _ = target_arr.shape
    mw, mh, _ = master_rgb.shape

    # 1. Build an expanded lookup table
    # Key: Tile bytes, Value: The specific index grid for that orientation
    tile_lookup = {}
    
    for y in range(0, mw, 8):
        for x in range(0, mh, 8):
            rgb_tile = master_rgb[y:y+8, x:x+8]
            idx_tile = master_indices[y:y+8, x:x+8]

            # Define the 4 transformations (Original, H-Flip, V-Flip, Both)
            # Use axis 1 for Horizontal (X), axis 0 for Vertical (Y)
            transforms = [
                (rgb_tile, idx_tile), # Original
                (np.flip(rgb_tile, axis=1), np.flip(idx_tile, axis=1)), # H-Flip
                (np.flip(rgb_tile, axis=0), np.flip(idx_tile, axis=0)), # V-Flip
                (np.flip(rgb_tile, axis=(0, 1)), np.flip(idx_tile, axis=(0, 1))) # Both
            ]

            for r_t, i_t in transforms:
                key = r_t.tobytes()
                if key not in tile_lookup:
                    tile_lookup[key] = i_t

    # 2. Build the new indexed image
    new_indices = np.zeros((tw, th), dtype=np.uint8)

    for y in range(0, tw, 8):
        for x in range(0, th, 8):
            target_tile = target_arr[y:y+8, x:x+8]
            target_key = target_tile.tobytes()

            if target_key in tile_lookup:
                new_indices[y:y+8, x:x+8] = tile_lookup[target_key]
            else:
                print(f"Warning: Tile at {x},{y} not found (even with reflections).")
                new_indices[y:y+8, x:x+8] = 0

    result_img = Image.fromarray(new_indices, mode="P")
    result_img.putpalette(master_indexed_img.getpalette())
    
    return result_img

def export_anims(path, output_path, tiles_img):
    anim_src_root = os.path.join(path, "anim")
    anim_out_root = os.path.join(output_path, "anim")
    
    if not os.path.isdir(anim_src_root):
        return None

    for folder in sorted(os.listdir(anim_src_root)):
        folder_src_path = os.path.join(anim_src_root, folder)
        if not os.path.isdir(folder_src_path):
            continue

        ref_path = os.path.join(folder_src_path, "00.png")
        if not os.path.exists(ref_path): 
            continue

        # 1. Process image
        ref_img = Image.open(ref_path).convert("RGBA")
        indexed_ref_img = index_image_from_master(ref_img, tiles_img)
        
        # 2. Define the folder path (NOT the file path)
        folder_out_path = os.path.join(anim_out_root, folder)
        
        # 3. Create the directory safely
        os.makedirs(folder_out_path, exist_ok=True)
        
        # 4. Save the file inside that directory
        save_file_path = os.path.join(folder_out_path, "00.png")
        indexed_ref_img.save(save_file_path)

# ========================
# UPDATED IMAGE EXPORT
# ========================

def build_global_pil_palette(palettes):
    """
    Creates one large 256-color palette.
    Palettes 0-5 are placed at indices 0, 16, 32, 48, 64, 80.
    """
    flat = []
    # Loop through your 6 palettes
    for p in range(len(palettes)):
        for r, g, b in palettes[p]:
            flat.extend([r, g, b])
    
    # Fill the rest of the 256 slots with black to satisfy PIL
    remaining = (256 * 3) - len(flat)
    flat.extend([0] * remaining)
    return flat

def export_indexed_image(img, assignment, palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    w, h = img.size
    tiles_x = w // TILE_SIZE

    # 1. Create an 8-bit indexed image ("P")
    composite = Image.new("P", (w, h))
    
    # 2. Use the ACTUAL colors in the palette, not grayscale
    # This ensures the 'tiles.png' looks exactly like the original image
    composite.putpalette(build_global_pil_palette(palettes))

    for i, assigned_p in enumerate(assignment):
        # assigned_p is the palette index (0 through 5)
        palette = palettes[assigned_p]
        
        # Calculate the offset for this specific palette bank
        # Palette 0 starts at index 0, Palette 1 at index 16, etc.
        palette_offset = assigned_p * 16

        tx = (i % tiles_x) * TILE_SIZE
        ty = (i // tiles_x) * TILE_SIZE

        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                raw = img.getpixel((tx + x, ty + y))

                # Find the local index (0-15)
                if raw == MAGENTA:
                    local_idx = 0
                else:
                    local_idx = nearest_palette_index(raw, palette)
                
                # 3. Apply the offset to get the global index (0-95)
                global_idx = palette_offset + local_idx
                composite.putpixel((tx + x, ty + y), global_idx)

    # Save as 8-bit (remove bits=4)
    composite.save(os.path.join(out_dir, "tiles.png"))
    return composite