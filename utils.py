from PIL import Image
import os
import numpy as np

def to_gba(color):
    r, g, b = color[:3]
    return ((r // 8) * 8, (g // 8) * 8, (b // 8) * 8)

def from_gba_value(val):
    """
    Reverts (val // 8) * 8 by stretching the 5-bit result 
    back to a full 8-bit 0-255 range.
    """
    five_bit = val // 8
    return (five_bit * 255) // 31

def color_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))

def nearest_palette_index(color, palette):
    best_idx, best_dist = 1, float("inf")
    for i, pc in enumerate(palette):
        dist = color_distance(color, pc)
        if dist < best_dist:
            best_idx, best_dist = i, dist
    return best_idx

def vconcat_indexed(img1, img2):
    """
    Vertically concatenate two PIL images in 'P' mode (indexed PNG).
    
    If palettes match → preserves indices exactly.
    If palettes differ → remaps img2 to img1's palette.
    """
    if img1.mode != "P" or img2.mode != "P":
        raise ValueError("Both images must be in 'P' (indexed) mode")

    # Copy to avoid modifying originals
    img1 = img1.copy()
    img2 = img2.copy()

    #palette1 = img1.getpalette()
    #palette2 = img2.getpalette()
    # If palettes differ, remap img2 to img1's palette
    #if palette1 != palette2:
    #    img2 = img2.quantize(palette=img1)

    # Create output image
    w = max(img1.width, img2.width)
    h = img1.height + img2.height

    out = Image.new("P", (w, h))
    out.putpalette(img1.getpalette())

    # Paste images
    out.paste(img1, (0, 0))
    out.paste(img2, (0, img1.height))

    return out

def match_palettes_by_tiles(original_img, indexed_img, palettes):
    # 1. Convert Original to RGB NumPy array
    if hasattr(original_img, "convert"):
        original_img = np.array(original_img.convert("RGB"))
    else:
        original_img = np.asarray(original_img)

    # 2. Convert Indexed image carefully
    if hasattr(indexed_img, "convert"):
        # If the image is already in 'P' (Palette) mode, this gets the raw indices.
        # Otherwise, 'L' is used, but we must ensure values are 0-15.
        indexed_img = np.array(indexed_img)
    else:
        indexed_img = np.asarray(indexed_img)

    h, w, _ = original_img.shape
    palette_indices = []
    
    np_palettes = {k: np.array(v, dtype=np.uint8) for k, v in palettes.items()}

    for y in range(0, h, 8):
        for x in range(0, w, 8):
            original_tile = original_img[y:y+8, x:x+8]
            indexed_tile = indexed_img[y:y+8, x:x+8]
            
            # --- DEBUG CHECK ---
            # If you still get the error, this will tell you exactly which tile is bad
            if indexed_tile.max() >= 16:
                # Force indices into 0-15 range to prevent crashing, 
                # though this tile will likely fail to match.
                indexed_tile = indexed_tile % 16 
            
            found_match = False
            for pal_idx, colors in np_palettes.items():
                # Apply palette
                colored_tile = colors[indexed_tile]
                
                if np.array_equal(original_tile, colored_tile):
                    palette_indices.append(pal_idx)
                    found_match = True
                    break
            
            if not found_match:
                palette_indices.append(None) 
                #palette_indices.append(0) 
                
    return palette_indices

def create_tileset_library(tiles_png_path, palettes):
    if not os.path.exists(tiles_png_path):
        return {}

    base_img = Image.open(tiles_png_path)
    library = {}

    for pal_id, pal_data in palettes.items():
        version = base_img.copy()
        version.putpalette(pal_data)
        rgba = version.convert("RGBA")
        new_pixels = [
			#(r, g, b, 255) if idx == 0 else (r, g, b, a)
			(r, g, b, 255)
			for idx, (r, g, b, a) in zip(base_img.getdata(), rgba.getdata())
		]

        rgba.putdata(new_pixels)
        library[pal_id] = rgba

    return library