import os
import struct
from PIL import Image, ImageOps

TILE_SIZE = 8
METATILE_SIZE = 16

def load_palette_images(path, count):
    palette_images = []
    for i in range(count):
        img_path = os.path.join(path, f"tiles_palette_{i}.png")
        if os.path.exists(img_path):
            palette_images.append(Image.open(img_path).convert("P"))
        else:
            print(f"Warning: Palette image {img_path} not found.")
    return palette_images

def compute_palette_per_tile(tiles_img, palette_images):
    w, h = tiles_img.size
    tiles_x = w // TILE_SIZE
    tiles_y = h // TILE_SIZE
    result = []
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            best_palette, best_score = 0, float("inf")
            for p_idx, pal_img in enumerate(palette_images):
                score = 0
                for y in range(TILE_SIZE):
                    for x in range(TILE_SIZE):
                        rgba = tiles_img.getpixel((tx * TILE_SIZE + x, ty * TILE_SIZE + y))
                        if rgba[3] < 128: continue 
                        pal_pixel_idx = pal_img.getpixel((tx * TILE_SIZE + x, ty * TILE_SIZE + y))
                        if pal_pixel_idx == 0: continue
                        palette_data = pal_img.getpalette()
                        pr, pg, pb = palette_data[pal_pixel_idx*3 : pal_pixel_idx*3 + 3]
                        score += (rgba[0] - pr)**2 + (rgba[1] - pg)**2 + (rgba[2] - pb)**2
                if score < best_score:
                    best_score, best_palette = score, p_idx
            result.append(best_palette)
    return result

###
def compute_tile_palette_map(ref_img, palette_images):
    w, h = ref_img.size
    tiles_x = w // TILE_SIZE
    tiles_y = h // TILE_SIZE

    assignment = []

    def get_palette_rgb(img, index):
        pal = img.getpalette()
        i = index * 3
        return (pal[i], pal[i+1], pal[i+2])

    def pixel_error(c1, c2):
        return sum((a - b) ** 2 for a, b in zip(c1, c2))

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

                        ref_pixel = ref_img.getpixel((px, py))

                        # Handle RGBA
                        if len(ref_pixel) == 4:
                            r, g, b, a = ref_pixel
                            if a == 0:
                                continue
                            ref_rgb = (r, g, b)
                        else:
                            ref_rgb = ref_pixel

                        pal_index = pal_img.getpixel((px, py))

                        if pal_index == 0:
                            continue  # transparent

                        pal_rgb = get_palette_rgb(pal_img, pal_index)

                        score += pixel_error(ref_rgb, pal_rgb)

                if score < best_score:
                    best_score = score
                    best_palette = p_idx

            assignment.append(best_palette)

    return assignment
###

def get_tile_lookup(unique_img, palette_list):
    lookup = {}
    
    # Calculate grid dimensions
    tiles_wide = unique_img.width // TILE_SIZE  # e.g., 128 // 8 = 16
    tiles_high = unique_img.height // TILE_SIZE # e.g., 256 // 8 = 32
    
    # Total number of 8x8 tiles in the unique_tiles image
    num_tiles = tiles_wide * tiles_high
    print(f"Indexing {num_tiles} unique tiles ({tiles_wide}x{tiles_high} grid)...")

    for i in range(num_tiles):
        # Calculate the X and Y coordinate of the tile in the unique_tiles grid
        # i % 16 gives the column (0-15)
        # i // 16 gives the row (0-31)
        tx = (i % tiles_wide) * TILE_SIZE
        ty = (i // tiles_wide) * TILE_SIZE
        
        # Crop the 8x8 area
        base_tile = unique_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
        
        # Ensure we don't go out of range of the palette list
        pal_id = palette_list[i] if i < len(palette_list) else 0
        
        # Generate all 4 orientation variants for this specific tile
        for h_flip in [0, 1]:
            for v_flip in [0, 1]:
                t = base_tile
                if h_flip: t = ImageOps.mirror(t)
                if v_flip: t = ImageOps.flip(t)
                
                pixels = tuple(t.getdata())
                # If this specific visual pattern hasn't been seen yet, 
                # map it back to the original tile index (i) and the required flips
                if pixels not in lookup:
                    lookup[pixels] = (i, pal_id, h_flip, v_flip)
                    
    return lookup

def build_metatiles_bin(bottom_path, middle_path, top_path, unique_path, palette_folder, output_path):
    # Load and prep images
    bottom_img = Image.open(bottom_path).convert("RGBA")
    mid_img = Image.open(middle_path).convert("RGBA")
    top_img = Image.open(top_path).convert("RGBA")
    unique_img = Image.open(unique_path).convert("RGBA")
    
    # Merge Middle and Top into a single "Upper" layer for Pokeemerald
    #upper_img = Image.alpha_composite(mid_img, top_img)
    upper_img = top_img
    
    pal_imgs = load_palette_images(palette_folder, 6)
    #palette_list = compute_palette_per_tile(unique_img, pal_imgs)
    palette_list = compute_tile_palette_map(unique_img, pal_imgs)
    print(palette_list)
    tile_lookup = get_tile_lookup(unique_img, palette_list)
    
    bin_data = bytearray()

    def get_tile_value(img, tx, ty):
        quad = img.crop((tx, ty, tx + 8, ty + 8))
        pix = tuple(quad.getdata())

        # Check if tile is completely transparent
        #if all(p[3] < 10 for p in pix):
        #    return 0

        if pix in tile_lookup:
            # 'idx' here is the index in your unique_tiles.png
            idx, pal, h, v = tile_lookup[pix]
            
            # Return the 16-bit GBA value
            return (pal << 12) | (v << 11) | (h << 10) | (idx & 0x3FF)
        
        return 0

    print("Encoding metatiles...")
    for y in range(0, bottom_img.height, METATILE_SIZE):
        for x in range(0, bottom_img.width, METATILE_SIZE):
            
            # 1. LAYER 1 (Bottom) - 4 tiles
            for ty in [0, 8]:
                for tx in [0, 8]:
                    val = get_tile_value(bottom_img, x + tx, y + ty)
                    bin_data.extend(struct.pack('<H', val))
            
            # 2. LAYER 2 (Upper/Top) - 4 tiles
            for ty in [0, 8]:
                for tx in [0, 8]:
                    val = get_tile_value(upper_img, x + tx, y + ty)
                    bin_data.extend(struct.pack('<H', val))

    with open(output_path, "wb") as f:
        f.write(bin_data)
    print(f"Success! {output_path} generated.")

if __name__ == "__main__":
    build_metatiles_bin(
        bottom_path="emerald/bottom.png",
        middle_path="emerald/middle.png",
        top_path="emerald/top.png",
        unique_path="emerald_out/unique_tiles.png",
        palette_folder="emerald_out",
        output_path="emerald_out/metatiles.bin"
    )