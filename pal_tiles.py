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