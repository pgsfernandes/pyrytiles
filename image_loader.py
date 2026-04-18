from tiles_dedup import dedup
from utils import to_gba
from config import TILE_SIZE, MAGENTA

# ========================
# TILE LOADING
# ========================
def load_tiles(path):
    input_paths = [f"{path}/{layer}.png" for layer in ("bottom", "middle", "top")]
    output_path = f"{path}/unique_tiles.png"

    img, _ = dedup(input_paths, output_path, False)
    img = img.convert("RGBA")

    tiles = []
    w, h = img.size

    for ty in range(0, h, TILE_SIZE):
        for tx in range(0, w, TILE_SIZE):
            colors = {
                img.getpixel((tx + x, ty + y))[:3]
                for y in range(TILE_SIZE)
                for x in range(TILE_SIZE)
                if img.getpixel((tx + x, ty + y))[3] != 0
            }

            colors.discard(MAGENTA)
            tiles.append(colors)

    return img, tiles