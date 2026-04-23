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

    # 2. Convert Indexed image to NumPy array
    # If this is a 'P' mode image, np.array() gives the raw 0-255 indices
    indexed_img = np.array(indexed_img)

    h, w, _ = original_img.shape
    palette_indices = []
    
    np_palettes = {k: np.array(v, dtype=np.uint8) for k, v in palettes.items()}

    for y in range(0, h, 8):
        for x in range(0, w, 8):
            original_tile = original_img[y:y+8, x:x+8]
            # This contains values like 0-95
            raw_indexed_tile = indexed_img[y:y+8, x:x+8]
            
            # Convert 0-95 indices back to 0-15 indices for color matching.
            # (e.g., Index 18 becomes Index 2)
            indexed_tile_16 = raw_indexed_tile % 16
            
            found_match = False
            for pal_idx, colors in np_palettes.items():
                # Now colors[indexed_tile_16] works because indices are 0-15
                colored_tile = colors[indexed_tile_16]
                
                if np.array_equal(original_tile, colored_tile):
                    palette_indices.append(pal_idx)
                    found_match = True
                    break
            
            if not found_match:
                palette_indices.append(None) 
                
    return palette_indices

def get_palette_indices_from_indexed(indexed_img):
    """
    Derives palette assignments directly from an 8-bit indexed image.
    Assumes indices 0-15 = Pal 0, 16-31 = Pal 1, etc.
    """
    # Convert PIL image to NumPy array of raw indices
    # (Image should be in 'P' mode)
    indices = np.array(indexed_img)
    
    h, w = indices.shape
    palette_indices = []

    for y in range(0, h, 8):
        for x in range(0, w, 8):
            # 1. Get the index of the top-left pixel of the 8x8 tile
            first_pixel_index = indices[y, x]
            
            # 2. Determine which palette bank it belongs to
            # e.g., 58 // 16 = 3 (Palette index 3)
            assigned_pal = int(first_pixel_index // 16)
            
            palette_indices.append(assigned_pal)
                
    return palette_indices

def create_tileset_library(tiles_png_path, palettes):
    if not os.path.exists(tiles_png_path):
        return {}

    base_img = Image.open(tiles_png_path).convert("P")
    library = {}

    # Convert the base image indices to 0-15 range immediately
    # This allows us to apply any 16-color palette to the shapes
    indices = np.array(base_img)
    normalized_indices = indices % 16
    normalized_img = Image.fromarray(normalized_indices, mode="P")

    for pal_id, pal_data in palettes.items():
        # Create a copy of the normalized (0-15) image
        version = normalized_img.copy()
        
        # Apply the specific 16-color palette bank
        version.putpalette(pal_data)
        
        # Convert to RGBA so we can handle transparency
        rgba = version.convert("RGBA")
        
        # transparency logic: if index was 0 (or 16, 32, etc), make it transparent
        # In the GBA, color 0 of any palette bank is transparent
        new_pixels = []
        for idx, pixel in zip(indices.flatten(), rgba.getdata()):
            if idx % 16 == 0:
                #new_pixels.append((0, 0, 0, 0)) # Fully transparent
                new_pixels.append((255, 0, 255, 255)) # Fully transparent
            else:
                new_pixels.append(pixel)

        rgba.putdata(new_pixels)
        library[pal_id] = rgba

    return library

def join_palettes(list_palettes: list, dict_palettes: dict) -> list:
    """
    Prepends dict_palettes to list_palettes, returning a single list of lists.

    :param list_palettes: list of lists of (R, G, B) tuples (e.g. from build_palettes)
    :param dict_palettes: dict mapping int -> set of (R, G, B) tuples (e.g. from load_jasc_pals)
    :return: list of lists of (R, G, B) tuples
    """
    joined = []

    for pal_id in sorted(dict_palettes.keys()):
        joined.append(list(dict_palettes[pal_id]))

    joined.extend(list_palettes)

    return joined

def compare_tile_colors_to_palettes(tile_color_sets: list, palettes: dict) -> dict:
    """
    Compares each tile's color set against all palettes.

    :param tile_color_sets: list of sets of (R, G, B) tuples, one per tile
    :param palettes: dict mapping palette_id -> set/list of (R, G, B) tuples
    :return: dict with per-tile results and a summary
    """
    results = []

    for i, tile_colors in enumerate(tile_color_sets):
        matching_palettes = []
        best_palette = None
        best_missing = None

        for pal_id, pal_colors in palettes.items():
            pal_set = set(pal_colors)
            missing = tile_colors - pal_set

            if not missing:
                matching_palettes.append(pal_id)
            else:
                if best_missing is None or len(missing) < len(best_missing):
                    best_missing = missing
                    best_palette = pal_id

        fits = len(matching_palettes) > 0
        results.append({
            "tile_index":         i,
            "fits":               fits,
            "matching_palettes":  matching_palettes,
            "closest_palette":    best_palette if not fits else None,
            "missing_colors":     best_missing if not fits else set(),
        })

    total = len(results)
    fitting = sum(1 for r in results if r["fits"])

    summary = {
        "total_tiles":       total,
        "fitting_tiles":     fitting,
        "non_fitting_tiles": total - fitting,
    }

    return {"results": results, "summary": summary}
'''
def load_jasc_pal(pal_path: str) -> list:
    """
    Loads a JASC-PAL file and returns its colors as a list of (R, G, B) tuples,
    preserving order.
    """
    with open(pal_path, "r") as f:
        lines = [line.strip() for line in f.readlines()]

    if lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError(f"Invalid JASC-PAL file: {pal_path}")

    num_colors = int(lines[2])

    colors = []
    for line in lines[3:3 + num_colors]:
        r, g, b = map(int, line.split())
        colors.append((r, g, b))

    return colors
'''
def load_jasc_pal(pal_path: str) -> list:
    """
    Loads a JASC-PAL file and returns its colors as a list of (R, G, B) tuples,
    preserving order, with the first color forced to Magenta (255, 0, 255).
    """
    with open(pal_path, "r") as f:
        lines = [line.strip() for line in f.readlines()]

    if lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError(f"Invalid JASC-PAL file: {pal_path}")

    num_colors = int(lines[2])

    colors = []
    for line in lines[3:3 + num_colors]:
        r, g, b = map(int, line.split())
        colors.append((r, g, b))

    # --- THE CHANGE ---
    if len(colors) > 0:
        colors[0] = (255, 0, 255)

    return colors

def load_jasc_pals_from_dir(pal_dir: str, max_index: int = 5) -> dict:
    """
    Loads JASC-PAL files from a directory, optionally filtering by index.
    
    :param pal_dir: path to directory containing .pal files
    :param max_index: if set, only loads palettes with numeric index <= max_index
    :return: dict mapping palette filename (without extension) -> set of (R, G, B) tuples
    """
    palettes = {}
    for fname in sorted(os.listdir(pal_dir)):
        if fname.endswith(".pal"):
            pal_id = os.path.splitext(fname)[0]
            if max_index is not None:
                try:
                    if int(pal_id) > max_index:
                        continue
                except ValueError:
                    continue  # skip non-numeric filenames
            palettes[int(pal_id)] = load_jasc_pal(os.path.join(pal_dir, fname))
    return palettes