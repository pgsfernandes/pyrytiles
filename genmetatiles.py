from PIL import Image, ImageOps
import struct
import os

TILE_SIZE = 8
METATILE_SIZE = 16


# ----------------------------
# TILE HELPERS
# ----------------------------
def get_variants(tile):
    return [
        (tile, (0, 0)),  # normal
        (ImageOps.mirror(tile), (1, 0)),  # hflip
        (ImageOps.flip(tile), (0, 1)),  # vflip
        (ImageOps.flip(ImageOps.mirror(tile)), (1, 1)),  # both
    ]


def build_tile_lookup(tiles_img):
    """
    Maps tile bytes -> (tile_index, (hflip, vflip))
    """
    lookup = {}

    tiles = []
    w, h = tiles_img.size

    # extract tiles
    for y in range(0, h, TILE_SIZE):
        for x in range(0, w, TILE_SIZE):
            tiles.append(
                tiles_img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
            )

    # build lookup including flips
    for idx, tile in enumerate(tiles):
        for variant, flips in get_variants(tile):
            key = variant.tobytes()

            # only store first match (important)
            if key not in lookup:
                lookup[key] = (idx, flips)

    return lookup


# ----------------------------
# METATILE EXTRACTION
# ----------------------------
def extract_metatile(layer, mx, my):
    return [
        layer.crop((mx, my, mx + 8, my + 8)),         # TL
        layer.crop((mx + 8, my, mx + 16, my + 8)),    # TR
        layer.crop((mx, my + 8, mx + 8, my + 16)),    # BL
        layer.crop((mx + 8, my + 8, mx + 16, my + 16))# BR
    ]


# ----------------------------
# PACKING (GBA FORMAT)
# ----------------------------
def pack(tile_index, hflip, vflip, palette=0):
    return (
        tile_index
        | (hflip << 10)
        | (vflip << 11)
        | (palette << 12)
    )


# ----------------------------
# MAIN FUNCTION
# ----------------------------
def build_metatiles_bin(tiles_img_path, bottom_path, middle_path, top_path, out_path):
    tiles_img = Image.open(tiles_img_path).convert("RGBA")
    bottom = Image.open(bottom_path).convert("RGBA")
    middle = Image.open(middle_path).convert("RGBA")
    top = Image.open(top_path).convert("RGBA")

    tile_lookup = build_tile_lookup(tiles_img)

    layers = [bottom, middle, top]

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with open(out_path, "wb") as f:

        for layer_idx, layer in enumerate(layers):

            w, h = layer.size

            for my in range(0, h, METATILE_SIZE):
                for mx in range(0, w, METATILE_SIZE):

                    tiles = extract_metatile(layer, mx, my)

                    packed = []

                    for tile in tiles:
                        key = tile.tobytes()

                        if key not in tile_lookup:
                            raise ValueError(
                                f"Tile not found in tileset "
                                f"(layer={layer_idx}, x={mx}, y={my})"
                            )

                        tile_index, (hflip, vflip) = tile_lookup[key]

                        packed.append(pack(tile_index, hflip, vflip, palette=0))

                    # write 4 u16 per metatile
                    f.write(struct.pack("<4H", *packed))

    print(f"Saved metatiles → {out_path}")


# ----------------------------
# EXAMPLE USAGE
# ----------------------------
if __name__ == "__main__":
    build_metatiles_bin(
        tiles_img_path="output-emerald.png",
        bottom_path="emerald/bottom.png",
        middle_path="emerald/middle.png",
        top_path="emerald/top.png",
        out_path="metatiles.bin"
    )