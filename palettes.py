import os
from collections import defaultdict
from ortools.sat.python import cp_model
from PIL import Image, ImageOps
#from tiles_dedup import dedup
import tiles_dedup

import struct

# ========================
# CONFIG
# ========================
TILE_SIZE = 8
METATILE_SIZE = 16
NUM_PALETTES = 6
MAX_COLORS = 15

MAGENTA = (255, 0, 255)


# ========================
# GBA COLOR QUANTIZATION
# ========================
def to_gba(c):
    r, g, b = c[:3]  # ignore alpha if present
    return ((r // 8) * 8, (g // 8) * 8, (b // 8) * 8)


def color_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def nearest_palette_index(color, palette):
    """Return index of nearest color in palette (skipping index 0 = magenta/transparent)."""
    best_idx = 1
    best_dist = float("inf")
    for i, pc in enumerate(palette):
        d = color_distance(color, pc)
        if d < best_dist:
            best_dist = d
            best_idx = i
    return best_idx

# ========================
# LOAD IMAGE AS TILES
# ========================
def load_tiles(path):
    input_paths = [
        path + "/bottom.png",
        path + "/middle.png",
        path + "/top.png"
    ]
    output_path = path + "/unique_tiles.png"
    img, tilesunique = tiles_dedup.dedup(input_paths,output_path,False)
    #img.save("emerald_out/unique_tiles_new.png")
    img = img.convert("RGBA")
    w, h = img.size

    tiles = []

    for ty in range(0, h, TILE_SIZE):
        for tx in range(0, w, TILE_SIZE):
            colors = set()

            for y in range(TILE_SIZE):
                for x in range(TILE_SIZE):
                    #c = to_gba(img.getpixel((tx + x, ty + y)))
                    r, g, b, a = img.getpixel((tx + x, ty + y))

                    if a == 0:
                        continue  # fully transparent → ignore
                    c = to_gba((r, g, b))

                    if c != to_gba(MAGENTA):
                        colors.add(c)

            tiles.append(colors)

    return img, tiles


# ========================
# OR-TOOLS MODEL
# ========================
def solve(path,max_time):
    img, tiles = load_tiles(path)
    n = len(tiles)

    model = cp_model.CpModel()

    # x[t,p] = tile t assigned to palette p
    x = {}
    for t in range(n):
        for p in range(NUM_PALETTES):
            x[t, p] = model.NewBoolVar(f"x_{t}_{p}")

    # each tile exactly one palette
    for t in range(n):
        model.Add(sum(x[t, p] for p in range(NUM_PALETTES)) == 1)

    # palette color usage tracking
    colors = sorted(set(c for t in tiles for c in t))
    used = {}

    for p in range(NUM_PALETTES):
        for c in colors:
            used[p, c] = model.NewBoolVar(f"u_{p}_{hash(c)}")

    # link tile assignment → palette uses color
    for p in range(NUM_PALETTES):
        for c in colors:
            tiles_with_c = [t for t in range(n) if c in tiles[t]]

            if tiles_with_c:
                model.AddMaxEquality(
                    used[p, c],
                    [x[t, p] for t in tiles_with_c]
                )
            else:
                model.Add(used[p, c] == 0)

    # palette color limit
    for p in range(NUM_PALETTES):
        model.Add(sum(used[p, c] for c in colors) <= MAX_COLORS)

    # objective: minimize color usage
    model.Minimize(
        sum(used[p, c] for p in range(NUM_PALETTES) for c in colors)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time

    print("Solving...")

    status = solver.Solve(model)

    if status == cp_model.OPTIMAL:
        print("Probably optimal")
    elif status == cp_model.FEASIBLE:
        print("A solution was found but may not be optimal")
    else:
        print("No solution found within time limit — problem may still be feasible")
        return None

    assignment = []

    for t in range(n):
        for p in range(NUM_PALETTES):
            if solver.Value(x[t, p]):
                assignment.append(p)
                break

    print("Solved!")
    return img, tiles, assignment


# ========================
# BUILD PALETTES
# ========================
def build_palettes(tiles, assignment):
    palettes = defaultdict(set)

    for tile, p in zip(tiles, assignment):
        palettes[p] |= tile

    final = []

    for p in range(NUM_PALETTES):
        colors = list(palettes[p])[:MAX_COLORS]
        colors = [to_gba(c) for c in colors]

        palette = [to_gba(MAGENTA)] + colors

        while len(palette) < 16:
            palette.append((0, 0, 0))

        final.append(palette)

    return final


# ========================
# EXPORT JASC-PAL
# ========================
def export_jasc(palettes, out_dir="out"):
    os.makedirs(out_dir, exist_ok=True)

    for i, pal in enumerate(palettes):
        path = os.path.join(out_dir, f"0{i}.pal")

        with open(path, "w") as f:
            f.write("JASC-PAL\n")
            f.write("0100\n")
            f.write("16\n")

            for r, g, b in pal:
                f.write(f"{r} {g} {b}\n")

    print(f"Exported {len(palettes)} palettes → {out_dir}")


# ========================
# EXPORT INDEXED IMAGE
# ========================

def export_indexed_image(img, assignment, palettes, out_dir="out"):
    os.makedirs(out_dir, exist_ok=True)

    w, h = img.size
    gba_magenta = to_gba(MAGENTA)
    tiles_x = w // TILE_SIZE

    def build_pil_palette(pal):
        flat = []
        for r, g, b in pal:
            flat.extend([r, g, b])

        while len(flat) < 256 * 3:
            flat.extend([0, 0, 0])

        return flat

    # ==================================================
    # 1. FULL COMPOSITE PER PALETTE
    # ==================================================
    '''
    for p_idx, palette in enumerate(palettes):

        composite = Image.new("P", (w, h), 0)
        composite.putpalette(build_pil_palette(palette))

        for tile_idx, assigned_p in enumerate(assignment):

            tx = (tile_idx % tiles_x) * TILE_SIZE
            ty = (tile_idx // tiles_x) * TILE_SIZE

            for y in range(TILE_SIZE):
                for x in range(TILE_SIZE):

                    #raw = to_gba(img.getpixel((tx + x, ty + y)))
                    r, g, b, a = img.getpixel((tx + x, ty + y))

                    if a == 0:
                        color_index = 0
                    else:
                        raw = to_gba((r, g, b))
                        color_index = nearest_palette_index(raw, palette)

                    if raw == gba_magenta:
                        color_index = 0
                    else:
                        color_index = nearest_palette_index(raw, palette)

                    composite.putpixel((tx + x, ty + y), color_index)

        composite.save(
            os.path.join(out_dir, f"tiles_palette_{p_idx}.png"),
            bits=4
        )
        '''

    # ==================================================
    # 2. BEST-PALETTE COMPOSITE (your original tiles.png)
    # ==================================================
    def count_real_colors(pal):
        return len([c for i, c in enumerate(pal) if i != 0 and c != (0, 0, 0)])

    best_idx, best_palette = max(
        enumerate(palettes),
        key=lambda x: count_real_colors(x[1])
    )

    composite = Image.new("P", (w, h), 0)
    composite.putpalette(build_pil_palette(best_palette))

    for tile_idx, assigned_p in enumerate(assignment):

        palette = palettes[assigned_p]

        tx = (tile_idx % tiles_x) * TILE_SIZE
        ty = (tile_idx // tiles_x) * TILE_SIZE

        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):

                raw = to_gba(img.getpixel((tx + x, ty + y)))

                if raw == gba_magenta:
                    color_index = 0
                else:
                    color_index = nearest_palette_index(raw, palette)

                composite.putpixel((tx + x, ty + y), color_index)

    composite.save(
        os.path.join(out_dir, "tiles.png"),
        bits=4
    )

    print(f"Exported {len(palettes)} palette composites + best composite → {out_dir}")

# ========================
# BIN
# ========================

def is_metatile_empty(img, x, y):
    """Checks if a 16x16 area is entirely Magenta (255, 0, 255)."""
    #MAGENTA = (255, 0, 255)
    MAGENTA = (248, 0, 248)
    # Convert crop to RGB and get data to check pixels
    patch = img.crop((x, y, x + 16, y + 16)).convert("RGB")
    pixels = list(patch.getdata())
    return all(p == MAGENTA for p in pixels)

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

def build_metatiles_bin(path, unique_img, palette_list, output_path):
    # Load and prep images
    bottom_img = Image.open(path + "/bottom.png").convert("RGBA")
    mid_img = Image.open(path + "/middle.png").convert("RGBA")
    top_img = Image.open(path + "/top.png").convert("RGBA")
    
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

    #with open(output_path, "wb") as f:
    #    f.write(bin_data)
    #print(f"Success! {output_path} generated.")

    full_file_path = os.path.join(output_path, "metatiles.bin")

    with open(full_file_path, "wb") as f:
        f.write(bin_data)

    print(f"Success! {full_file_path} generated.")

# ========================
# MAIN
# ========================
def main(path, out_dir):
    max_time = 1.0 # Increased time slightly for better results
    result = solve(path, max_time)

    os.makedirs(out_dir, exist_ok=True)

    if result is None:
        return

    img, tiles, assignment = result

    # === NEW CODE TO EXPORT ASSIGNMENTS ===
    with open(os.path.join(out_dir, "tile_assignments.txt"), "w") as f:
        # Option A: A simple space-separated list (good for code reading)
        f.write(" ".join(map(str, assignment)))
        
        # Option B: One per line if you prefer
        # for a in assignment: f.write(f"{a}\n")
    
    print(f"Exported tile palette assignments to {out_dir}/tile_assignments.txt")
    # ======================================

    img.save(out_dir+"/unique_tiles.png")
    palettes = build_palettes(tiles, assignment)
    export_jasc(palettes, out_dir)
    export_indexed_image(img, assignment, palettes, out_dir)
    build_metatiles_bin(path,img,assignment,out_dir)


if __name__ == "__main__":
    main("emerald","emerald_out")