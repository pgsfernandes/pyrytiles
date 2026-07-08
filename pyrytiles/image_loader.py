from .tiles_dedup import dedup, dedup_from_imgs
from .config import TILE_SIZE, MAGENTA, get_game_profile

# ========================
# TILE LOADING
# ========================
def load_tiles(path, max_tiles=None):
    if max_tiles is None:
        max_tiles = get_game_profile("emerald")["primary_tile_count"]

    input_paths = [f"{path}/{layer}.png" for layer in ("bottom", "middle", "top")]

    img = dedup(input_paths, max_tiles)
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

def load_tiles_from_imgs(imgs, max_tiles=None):
    if max_tiles is None:
        max_tiles = get_game_profile("emerald")["primary_tile_count"]

    img, _ = dedup_from_imgs(imgs, max_tiles)
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

    return img
