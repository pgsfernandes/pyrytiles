import os
from PIL import Image
from collections import defaultdict
from utils import to_gba, nearest_palette_index
from config import *

# ========================
# PALETTE BUILDING
# ========================
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
        for i in range(12):
            filename = f"{i:02d}.pal"
            path = os.path.join(out_dir, filename)

            if 6 <= i <= 11:
                write_pal(path, primary_marked_pal)
            else:
                write_pal(path, palettes[i])
    else:
        for i in range(12):
            filename = f"{i:02d}.pal"
            path = os.path.join(out_dir, filename)

            if 0 <= i <= 5:
                write_pal(path, empty_pal)
            else:
                write_pal(path, palettes[i - 6])

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
                raw = img.getpixel((tx + x, ty + y))

                idx = 0 if raw == MAGENTA else nearest_palette_index(raw, palette)
                composite.putpixel((tx + x, ty + y), idx)

    composite.save(os.path.join(out_dir, "tiles.png"), bits=4)

def export_indexed_image_secondary(img, assignment, palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    w, h = img.size
    tiles_x = w // TILE_SIZE

    best_palette = max(
        palettes[6:12],
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
                raw = img.getpixel((tx + x, ty + y))

                idx = 0 if raw == MAGENTA else nearest_palette_index(raw, palette)
                composite.putpixel((tx + x, ty + y), idx)

    composite.save(os.path.join(out_dir, "tiles.png"), bits=4)