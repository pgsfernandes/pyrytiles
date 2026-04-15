from pathlib import Path
import numpy as np
from PIL import Image


def find_tile_palettes(
    tiles_path: str,
    palette_folder: str,
    tile_size: int = 8,
    num_palettes: int = 6,
) -> list[int]:
    """
    For each 8x8 tile in tiles_path, find which palette image (0..num_palettes-1)
    has the closest matching color for that tile.

    Args:
        tiles_path:      Path to the reference tiles image.
        palette_folder:  Folder containing tiles_palette_0.png … tiles_palette_N.png
        tile_size:       Size of each square tile in pixels (default 8).
        num_palettes:    Number of palette images (default 5).

    Returns:
        A flat list of ints, one per tile (row-major order), giving the index
        of the palette whose tile color best matches the reference.
    """
    ref = np.array(Image.open(tiles_path).convert("RGB"), dtype=np.int32)
    h, w = ref.shape[:2]

    tiles_y = h // tile_size
    tiles_x = w // tile_size
    num_tiles = tiles_y * tiles_x

    folder = Path(palette_folder)
    palettes = [
        np.array(
            Image.open(folder / f"tiles_palette_{i}.png").convert("RGB"),
            dtype=np.int32,
        )
        for i in range(num_palettes)
    ]

    # Shape: (num_palettes, num_tiles) — MSE of each palette tile vs reference tile
    errors = np.zeros((num_palettes, num_tiles), dtype=np.float64)

    tile_idx = 0
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            y0, y1 = ty * tile_size, (ty + 1) * tile_size
            x0, x1 = tx * tile_size, (tx + 1) * tile_size

            ref_tile = ref[y0:y1, x0:x1]  # (tile_size, tile_size, 3)

            for p, pal in enumerate(palettes):
                diff = pal[y0:y1, x0:x1] - ref_tile
                errors[p, tile_idx] = np.mean(diff ** 2)

            tile_idx += 1

    # For each tile pick the palette with the lowest MSE
    best_palette = np.argmin(errors, axis=0).tolist()
    return best_palette


# ── quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python tile_palette_matcher.py <tiles.png> <palette_folder>")
        sys.exit(1)

    result = find_tile_palettes(sys.argv[1], sys.argv[2])
    print(f"Palette indices per tile ({len(result)} tiles):")
    print(result)