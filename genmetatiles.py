from PIL import Image, ImageOps
import struct
import os

TILE_SIZE = 8
METATILE_SIZE = 16


# ============================
# NORMALIZATION
# ============================
def normalize_tile(tile):
    tile = tile.convert("RGBA")

    out = []
    for (r, g, b, a) in tile.getdata():
        if a == 0:
            out.append((0, 0, 0, 0))
        else:
            out.append((r, g, b, 255))

    return bytes([c for px in out for c in px])


def is_empty_tile(tile):
    tile = tile.convert("RGBA")
    return all(a == 0 for (_, _, _, a) in tile.getdata())


# ============================
# TILE VARIANTS
# ============================
def get_variants(tile):
    return [
        (tile, (0, 0)),
        (ImageOps.mirror(tile), (1, 0)),
        (ImageOps.flip(tile), (0, 1)),
        (ImageOps.flip(ImageOps.mirror(tile)), (1, 1)),
    ]


def build_tile_lookup(tiles_img):
    lookup = {}
    tiles = []

    w, h = tiles_img.size

    for y in range(0, h, TILE_SIZE):
        for x in range(0, w, TILE_SIZE):
            tiles.append(
                tiles_img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
            )

    for idx, tile in enumerate(tiles):
        for variant, flips in get_variants(tile):
            key = normalize_tile(variant)
            if key not in lookup:
                lookup[key] = (idx, flips)

    return lookup


# ============================
# METATILE EXTRACTION
# ============================
def extract_metatile(layer, mx, my):
    return [
        layer.crop((mx, my, mx + 8, my + 8)),          # TL
        layer.crop((mx + 8, my, mx + 16, my + 8)),     # TR
        layer.crop((mx, my + 8, mx + 8, my + 16)),     # BL
        layer.crop((mx + 8, my + 8, mx + 16, my + 16)) # BR
    ]


def extract_layer_metatile(layer, mx, my):
    tiles = extract_metatile(layer, mx, my)

    if all(is_empty_tile(t) for t in tiles):
        return None

    return tiles


# ============================
# PACK FORMAT
# ============================
def pack(tile_index, hflip, vflip, palette):
    return (
        tile_index
        | (hflip << 10)
        | (vflip << 11)
        | (palette << 12)
    )


# ============================
# PALETTE LOADING
# ============================
def load_palette_images(path, count):
    return [
        Image.open(os.path.join(path, f"tiles_palette_{i}.png"))
        for i in range(count)
    ]


# ============================
# PALETTE PER TILE
# ============================
def compute_palette_per_tile(tiles_img, palette_images):
    w, h = tiles_img.size
    tiles_x = w // TILE_SIZE
    tiles_y = h // TILE_SIZE

    result = []

    for ty in range(tiles_y):
        for tx in range(tiles_x):

            best_palette = 0
            best_score = float("inf")

            for p_idx, pal_img in enumerate(palette_images):
                score = 0

                for y in range(TILE_SIZE):
                    for x in range(TILE_SIZE):

                        px = tx * TILE_SIZE + x
                        py = ty * TILE_SIZE + y

                        r, g, b, a = tiles_img.getpixel((px, py))

                        if a == 0:
                            continue

                        pal_index = pal_img.getpixel((px, py))
                        if pal_index == 0:
                            continue

                        pal = pal_img.getpalette()
                        i = pal_index * 3
                        pr, pg, pb = pal[i], pal[i+1], pal[i+2]

                        score += (r - pr)**2 + (g - pg)**2 + (b - pb)**2

                if score < best_score:
                    best_score = score
                    best_palette = p_idx

            result.append(best_palette)

    return result


# ============================
# MAIN BUILDER
# ============================
def build_metatiles_bin(
    tiles_img_path,
    bottom_path,
    middle_path,
    top_path,
    out_path,
    palettes_path
):
    tiles_img = Image.open(tiles_img_path).convert("RGBA")
    bottom = Image.open(bottom_path).convert("RGBA")
    middle = Image.open(middle_path).convert("RGBA")
    top = Image.open(top_path).convert("RGBA")

    # sanity checks (VERY IMPORTANT)
    assert bottom.size == middle.size == top.size, "Layer size mismatch"

    layers = [bottom]  # future: bottom/middle/top

    palette_images = load_palette_images(palettes_path, 6)
    tile_palette_vector = compute_palette_per_tile(tiles_img, palette_images)

    tile_lookup = build_tile_lookup(tiles_img)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    w, h = bottom.size

    with open(out_path, "wb") as f:

        # 1. METATILE GRID (CRITICAL)
        for my in range(0, h, METATILE_SIZE):
            for mx in range(0, w, METATILE_SIZE):

                # 2. EACH LAYER (kept for future)
                for layer_idx, layer in enumerate(layers):

                    # 3. extract 4 tiles in FIXED ORDER
                    tiles = [
                        # TL
                        layer.crop((mx, my, mx + 8, my + 8)),

                        # TR
                        layer.crop((mx + 8, my, mx + 16, my + 8)),

                        # BL
                        layer.crop((mx, my + 8, mx + 8, my + 16)),

                        # BR
                        layer.crop((mx + 8, my + 8, mx + 16, my + 16)),
                    ]

                    packed = []

                    for tile in tiles:
                        key = normalize_tile(tile)

                        if key not in tile_lookup:
                            raise ValueError(
                                f"Missing tile (layer={layer_idx}, mx={mx}, my={my})"
                            )

                        tile_index, (hflip, vflip) = tile_lookup[key]
                        palette = tile_palette_vector[tile_index]

                        packed.append(
                            pack(tile_index, hflip, vflip, palette)
                        )

                    # write exactly 4 tiles per layer
                    f.write(struct.pack("<4H", *packed))

    print(f"Saved metatiles → {out_path}")


# ============================
# RUN
# ============================
if __name__ == "__main__":
    build_metatiles_bin(
        tiles_img_path="emerald_out/unique_tiles.png",
        bottom_path="emerald/bottom.png",
        middle_path="emerald/middle.png",
        top_path="emerald/top.png",
        out_path="emerald_out/metatiles.bin",
        palettes_path="emerald_out"
    )