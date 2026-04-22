import os
from PIL import Image
import numpy as np

TILE_SIZE = 8
FIXED_WIDTH = 128
TILES_PER_ROW = 16

def is_filler(tile_array):
    """
    Returns True if the tile is likely background/empty.
    Adjust this logic if your 'empty' tiles are a specific color.
    """
    # Check if all pixels in the tile are identical (solid color)
    first_pixel = tile_array[0, 0]
    if np.all(tile_array == first_pixel):
        return True
    
    # Check if tile is fully transparent (if using Alpha)
    if tile_array.shape[2] == 4 and np.all(tile_array[:, :, 3] == 0):
        return True
        
    return False

def split_into_tiles(img):
    img = img.convert("RGBA")
    w, h = img.size
    rows = h // TILE_SIZE
    tiles = []
    for y in range(0, h, TILE_SIZE):
        for x in range(0, FIXED_WIDTH, TILE_SIZE):
            tile = img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
            tiles.append(np.array(tile))
    return tiles, rows

def reconstruct_image(tiles, rows):
    new_img = Image.new("RGBA", (FIXED_WIDTH, rows * TILE_SIZE))
    for i, tile_data in enumerate(tiles):
        if i >= rows * TILES_PER_ROW: break
        grid_x = (i % TILES_PER_ROW) * TILE_SIZE
        grid_y = (i // TILES_PER_ROW) * TILE_SIZE
        new_img.paste(Image.fromarray(tile_data), (grid_x, grid_y))
    return new_img

def process_image_shift(img, path_primary, *vectors):
    tiles, rows = split_into_tiles(img)
    working_vectors = [list(v) for v in vectors]

    anim_path = os.path.join(path_primary, "anim")
    if not os.path.isdir(anim_path):
        return reconstruct_image(tiles, rows), *working_vectors

    for folder in sorted(os.listdir(anim_path)):
        ref_path = os.path.join(anim_path, folder, "00.png")
        if not os.path.exists(ref_path): continue

        ref_img = Image.open(ref_path).convert("RGBA")
        ref_tiles, ref_rows = split_into_tiles(ref_img)

        for r in reversed(range(ref_rows)):
            for col in reversed(range(TILES_PER_ROW)):
                ref_tile = ref_tiles[r * TILES_PER_ROW + col]

                if is_filler(ref_tile):
                    continue

                for i in range(len(tiles)):
                    current_tile = tiles[i]
                    matched_flip = None

                    # 1. Check all 4 orientations (Original, H, V, HV)
                    # We store the flipped version so we can update the tiles list
                    potential_matches = [
                        (current_tile, "none"),
                        (np.flip(current_tile, axis=1), "h"),
                        (np.flip(current_tile, axis=0), "v"),
                        (np.flip(current_tile, axis=(0, 1)), "hv")
                    ]

                    for flipped_tile, name in potential_matches:
                        if np.array_equal(flipped_tile, ref_tile):
                            matched_flip = flipped_tile
                            break

                    if matched_flip is not None:
                        # --- THE SYNCED MOVE ---
                        # 1. Update the tile with the correctly oriented version
                        # (This ensures the reconstructed image matches the ref_tile exactly)
                        tiles[i] = matched_flip
                        
                        # 2. Move the tile array to the front (index 1 as per your original logic)
                        target_tile = tiles.pop(i)
                        tiles.insert(1, target_tile)
                        
                        # 3. Move the corresponding element in EVERY vector
                        for v_list in working_vectors:
                            item = v_list.pop(i)
                            v_list.insert(1, item)
                        
                        # Break the 'i' loop once matched
                        break

    return reconstruct_image(tiles, rows), *working_vectors