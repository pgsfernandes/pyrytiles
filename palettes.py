import os
from collections import defaultdict
from ortools.sat.python import cp_model
from PIL import Image
#from tiles_dedup import dedup
import tiles_dedup

# ========================
# CONFIG
# ========================
TILE_SIZE = 8
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


if __name__ == "__main__":
    main("emerald","emerald_out")