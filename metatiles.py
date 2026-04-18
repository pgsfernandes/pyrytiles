import os
import struct
import csv
from PIL import Image, ImageOps
from config import *

# ========================
# METATILE HELPERS
# ========================
def is_metatile_empty(img, x, y):
    mag = (255, 0, 255)
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

    # Load attributes from CSV
    attr_csv_path = os.path.join(path, "attributes.csv")
    attributes_list = []
    
    if os.path.exists(attr_csv_path):
        with open(attr_csv_path, "r") as f:
            reader = csv.reader(f)
            # Skip the header row (id,behavior)
            next(reader, None) 
            # Get the behavior string from the second column (row[1])
            for row in reader:
                if len(row) >= 2:
                    attributes_list.append(row[1].strip())

    lookup = get_tile_lookup(unique_img, palette_list)
    data = bytearray()       
    attr_data = bytearray()  

    print(f"Generating metatiles and attributes...")

    metatile_index = 0
    for y in range(0, bottom.height, METATILE_SIZE):
        for x in range(0, bottom.width, METATILE_SIZE):
            
            # --- Visual Encoding & Layer Attribute Logic ---
            if is_metatile_empty(bottom, x, y):
                layer_attr = 0x0000 
                encode_layer(middle, x, y, lookup, data)
                encode_layer(top, x, y, lookup, data)

            elif is_metatile_empty(middle, x, y):
                layer_attr = 0x2000
                encode_layer(bottom, x, y, lookup, data)
                encode_layer(top, x, y, lookup, data)

            else:
                layer_attr = 0x1000
                encode_layer(bottom, x, y, lookup, data)
                encode_layer(middle, x, y, lookup, data)

            # --- Attribute Binary Logic ---
            # Correctly pull from our cleaned attributes_list
            if metatile_index < len(attributes_list):
                behavior_name = attributes_list[metatile_index]
            else:
                behavior_name = "MB_NORMAL"
            
            behavior_id = BEHAVIOR_MAP.get(behavior_name, 0x00)
            
            # Final 16-bit value: [Layer (4 bits)][Terrain (4 bits)][Behavior (8 bits)]
            # Note: Since terrain is unused, behavior just sits in the bottom 8 bits.
            final_attribute = behavior_id | layer_attr
            
            attr_data.extend(struct.pack('<H', final_attribute))
            metatile_index += 1

    # Save visual tiles
    with open(os.path.join(out_dir, "metatiles.bin"), "wb") as f:
        f.write(data)

    # Save attributes
    with open(os.path.join(out_dir, "metatile_attributes.bin"), "wb") as f:
        f.write(attr_data)

    print(f"Successfully generated metatiles.bin and metatile_attributes.bin")