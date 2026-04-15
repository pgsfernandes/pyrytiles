import os
import struct
from collections import defaultdict

from ortools.sat.python import cp_model
from PIL import Image, ImageOps

import tiles_dedup


# ========================
# CONFIG
# ========================
TILE_SIZE = 8
METATILE_SIZE = 16

NUM_PALETTES = 6
MAX_COLORS = 15

MAGENTA = (255, 0, 255)


# ========================
# COLOR UTILS
# ========================
def to_gba(color):
    r, g, b = color[:3]
    return ((r // 8) * 8, (g // 8) * 8, (b // 8) * 8)


def color_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def nearest_palette_index(color, palette):
    best_idx, best_dist = 1, float("inf")

    for i, pc in enumerate(palette):
        dist = color_distance(color, pc)
        if dist < best_dist:
            best_idx, best_dist = i, dist

    return best_idx


# ========================
# TILE LOADING
# ========================
def load_tiles(path):
    input_paths = [f"{path}/{layer}.png" for layer in ("bottom", "middle", "top")]
    output_path = f"{path}/unique_tiles.png"

    img, _ = tiles_dedup.dedup(input_paths, output_path, False)
    img = img.convert("RGBA")

    tiles = []
    w, h = img.size

    for ty in range(0, h, TILE_SIZE):
        for tx in range(0, w, TILE_SIZE):
            colors = {
                to_gba(img.getpixel((tx + x, ty + y))[:3])
                for y in range(TILE_SIZE)
                for x in range(TILE_SIZE)
                if img.getpixel((tx + x, ty + y))[3] != 0
            }

            colors.discard(to_gba(MAGENTA))
            tiles.append(colors)

    return img, tiles


# ========================
# SOLVER
# ========================
def solve(path, max_time):
    img, tiles = load_tiles(path)
    n = len(tiles)

    model = cp_model.CpModel()

    x = {
        (t, p): model.NewBoolVar(f"x_{t}_{p}")
        for t in range(n)
        for p in range(NUM_PALETTES)
    }

    # each tile → one palette
    for t in range(n):
        model.Add(sum(x[t, p] for p in range(NUM_PALETTES)) == 1)

    colors = sorted({c for tile in tiles for c in tile})

    used = {
        (p, c): model.NewBoolVar(f"u_{p}_{hash(c)}")
        for p in range(NUM_PALETTES)
        for c in colors
    }

    for p in range(NUM_PALETTES):
        for c in colors:
            tiles_with_c = [t for t in range(n) if c in tiles[t]]

            if tiles_with_c:
                model.AddMaxEquality(used[p, c], [x[t, p] for t in tiles_with_c])
            else:
                model.Add(used[p, c] == 0)

        model.Add(sum(used[p, c] for c in colors) <= MAX_COLORS)

    model.Minimize(sum(used.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time

    print("Looking for a solution...")
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No solution found")
        return None

    assignment = [
        next(p for p in range(NUM_PALETTES) if solver.Value(x[t, p]))
        for t in range(n)
    ]

    print("Solution found!")
    return img, tiles, assignment


# ========================
# PALETTE BUILDING
# ========================
def build_palettes(tiles, assignment):
    palettes = defaultdict(set)

    for tile, p in zip(tiles, assignment):
        palettes[p] |= tile

    final = []

    for p in range(NUM_PALETTES):
        colors = [to_gba(c) for c in list(palettes[p])[:MAX_COLORS]]

        palette = [to_gba(MAGENTA)] + colors
        palette += [(0, 0, 0)] * (16 - len(palette))

        final.append(palette)

    return final


# ========================
# EXPORT PALETTE
# ========================
def export_jasc(palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    for i, pal in enumerate(palettes):
        filename = f"{i:02d}.pal"
        with open(os.path.join(out_dir, filename), "w") as f:
            f.write("JASC-PAL\n0100\n16\n")
            for r, g, b in pal:
                f.write(f"{r} {g} {b}\n")

    print("Palettes exported")


# ========================
# IMAGE EXPORT
# ========================
def build_pil_palette(palette):
    flat = [v for color in palette for v in color]
    flat += [0] * (256 * 3 - len(flat))
    return flat


def export_indexed_image(img, assignment, palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    w, h = img.size
    tiles_x = w // TILE_SIZE
    gba_magenta = to_gba(MAGENTA)

    best_palette = max(
        palettes,
        key=lambda p: sum(1 for i, c in enumerate(p) if i and c != (0, 0, 0))
    )

    composite = Image.new("P", (w, h))
    composite.putpalette(build_pil_palette(best_palette))

    for i, assigned_p in enumerate(assignment):
        palette = palettes[assigned_p]

        tx = (i % tiles_x) * TILE_SIZE
        ty = (i // tiles_x) * TILE_SIZE

        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                raw = to_gba(img.getpixel((tx + x, ty + y)))

                idx = 0 if raw == gba_magenta else nearest_palette_index(raw, palette)
                composite.putpixel((tx + x, ty + y), idx)

    composite.save(os.path.join(out_dir, "tiles.png"), bits=4)


# ========================
# METATILE HELPERS
# ========================
def is_metatile_empty(img, x, y):
    mag = (248, 0, 248)
    pixels = img.crop((x, y, x + 16, y + 16)).convert("RGB").getdata()
    return all(p == mag for p in pixels)


def get_tile_lookup(unique_img, palette_list):
    lookup = {}

    tiles_w = unique_img.width // TILE_SIZE
    tiles_h = unique_img.height // TILE_SIZE

    for i in range(tiles_w * tiles_h):
        tx = (i % tiles_w) * TILE_SIZE
        ty = (i // tiles_w) * TILE_SIZE

        base = unique_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
        pal = palette_list[i] if i < len(palette_list) else 0

        for h in (0, 1):
            for v in (0, 1):
                t = base
                if h: t = ImageOps.mirror(t)
                if v: t = ImageOps.flip(t)

                key = tuple(t.getdata())
                lookup.setdefault(key, (i, pal, h, v))

    return lookup


def encode_layer(img, x, y, lookup, out):
    for dy in (0, 8):
        for dx in (0, 8):
            quad = img.crop((x + dx, y + dy, x + dx + 8, y + dy + 8))
            key = tuple(quad.getdata())

            if key in lookup:
                idx, pal, h, v = lookup[key]
                val = (pal << 12) | (v << 11) | (h << 10) | (idx & 0x3FF)
            else:
                val = 0

            out.extend(struct.pack("<H", val))


# ========================
# METATILE BUILD
# ========================
def build_metatiles_bin(path, unique_img, palette_list, out_dir):
    bottom = Image.open(f"{path}/bottom.png").convert("RGBA")
    middle = Image.open(f"{path}/middle.png").convert("RGBA")
    top = Image.open(f"{path}/top.png").convert("RGBA")

    lookup = get_tile_lookup(unique_img, palette_list)
    data = bytearray()

    print("Encoding metatiles...")

    for y in range(0, bottom.height, METATILE_SIZE):
        for x in range(0, bottom.width, METATILE_SIZE):

            if is_metatile_empty(bottom, x, y):
                encode_layer(middle, x, y, lookup, data)
                encode_layer(top, x, y, lookup, data)

            elif is_metatile_empty(middle, x, y):
                encode_layer(bottom, x, y, lookup, data)
                encode_layer(top, x, y, lookup, data)

            else:
                encode_layer(bottom, x, y, lookup, data)
                encode_layer(middle, x, y, lookup, data)

    out_path = os.path.join(out_dir, "metatiles.bin")
    with open(out_path, "wb") as f:
        f.write(data)

    print(f"Generated metatiles.bin file")

# ========================
# MAIN
# ========================
def compile_primary(path, out_dir, time):
    result = solve(path, max_time=time)
    if result is None:
        return

    img, tiles, assignment = result

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir+"/palettes", exist_ok=True)

    palettes = build_palettes(tiles, assignment)

    export_jasc(palettes, out_dir+"/palettes")
    export_indexed_image(img, assignment, palettes, out_dir)
    build_metatiles_bin(path, img, assignment, out_dir)

#compile_primary("lightplat","lightplat_output",60.0)
#compile_primary("emerald","$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary",1.0)

input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/lightplat")
out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary")
compile_primary(input_dir,out_dir,1.0)