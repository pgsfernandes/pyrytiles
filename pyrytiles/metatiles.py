import os
import struct
import csv
from PIL import Image, ImageOps
from .config import *

# ========================
# METATILE HELPERS
# ========================
def is_metatile_empty(img, x, y):
    pixels = img.crop((x, y, x + 16, y + 16)).convert("RGB").getdata()
    return all(p == MAGENTA for p in pixels)


def get_tile_lookup(unique_img, palette_list, offset=0):
    lookup = {}
    tiles_w = unique_img.width // TILE_SIZE
    tiles_h = unique_img.height // TILE_SIZE

    for i in range(tiles_w * tiles_h):
        tx = (i % tiles_w) * TILE_SIZE
        ty = (i // tiles_w) * TILE_SIZE

        base = unique_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
        pal = palette_list[i] if i < len(palette_list) else 0

        # The tile index is now shifted by the offset
        vram_index = i + offset

        for h in (0, 1):
            for v in (0, 1):
                t = base
                if h: t = ImageOps.mirror(t)
                if v: t = ImageOps.flip(t)

                key = tuple(t.getdata())
                # Store the shifted index
                lookup.setdefault(key, (vram_index, pal, h, v))

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
def process_metatile_layers(bottom, middle, top, lookup, attributes_list, triple_layer=False):
    """
    Processes metatile images and attributes into binary data.
    Returns a tuple of (metatile_data, attribute_data).
    """
    data = bytearray()
    attr_data = bytearray()
    metatile_index = 0

    # Iterate through the tileset grid
    for y in range(0, bottom.height, METATILE_SIZE):
        for x in range(0, bottom.width, METATILE_SIZE):
            
            if triple_layer:
                # --- TRIPLE LAYER LOGIC ---
                # Fixed 24-byte structure: [Bottom][Middle][Top]
                encode_layer(bottom, x, y, lookup, data)
                encode_layer(middle, x, y, lookup, data)
                encode_layer(top, x, y, lookup, data)
                
                # Layer bits are ignored/zeroed in triple layer hacks
                layer_attr = 0 
            else:
                # --- ORIGINAL DUAL LAYER LOGIC ---
                # Uses 16-byte structure with attribute bits to determine layering
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

            # --- Attribute Logic ---
            if metatile_index < len(attributes_list):
                behavior_name = attributes_list[metatile_index]
            else:
                behavior_name = "MB_NORMAL"
            
            behavior_id = BEHAVIOR_MAP.get(behavior_name, 0x00)
            
            # Combine the behavior ID with the layer metadata
            final_attribute = behavior_id | layer_attr
            attr_data.extend(struct.pack('<H', final_attribute))
            
            metatile_index += 1

    return data, attr_data

def build_metatiles_bin(path, unique_img, palette_list, out_dir, triple_layer=False):
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
    
    data, attr_data = process_metatile_layers(
    bottom, middle, top, 
    lookup, attributes_list, 
    triple_layer=triple_layer
)

    # Save visual tiles
    with open(os.path.join(out_dir, "metatiles.bin"), "wb") as f:
        f.write(data)

    # Save attributes
    with open(os.path.join(out_dir, "metatile_attributes.bin"), "wb") as f:
        f.write(attr_data)

    print(f"Successfully generated metatiles.bin and metatile_attributes.bin")

# ========================
# METATILE HELPERS (SECONDARY)
# ========================
def encode_layer_secondary(img, x, y, secondary_lookup, primary_lookup, out, triple_layer=False):
    # Set the mask once per layer call instead of 4 times per layer
    #TILE_INDEX_MASK = 0x7FF if triple_layer else 0x3FF
    TILE_INDEX_MASK = 0x3FF
    
    for dy in (0, 8):
        for dx in (0, 8):
            quad = img.crop((x + dx, y + dy, x + dx + 8, y + dy + 8))
            key = tuple(quad.getdata())

            if key in secondary_lookup:
                idx, pal, h, v = secondary_lookup[key]
            elif key in primary_lookup:
                idx, pal, h, v = primary_lookup[key]
            else:
                idx, pal, h, v = 0, 0, 0, 0

            # Pack the 16-bit value
            val = (pal << 12) | (v << 11) | (h << 10) | (idx & TILE_INDEX_MASK)
            out.extend(struct.pack("<H", val))

def process_metatile_layers_secondary(bottom, middle, top, lookup, lookup_primary, attributes_list, triple_layer=False):
    """
    Generalized logic for secondary tilesets supporting Dual and Triple layers.
    """
    data = bytearray()
    attr_data = bytearray()
    metatile_index = 0

    for y in range(0, bottom.height, METATILE_SIZE):
        for x in range(0, bottom.width, METATILE_SIZE):
            
            if triple_layer:
                # --- TRIPLE LAYER LOGIC ---
                encode_layer_secondary(bottom, x, y, lookup, lookup_primary, data, True)
                encode_layer_secondary(middle, x, y, lookup, lookup_primary, data, True)
                encode_layer_secondary(top, x, y, lookup, lookup_primary, data, True)
                layer_attr = 0 
            else:
                # --- ORIGINAL DUAL LAYER LOGIC ---
                if is_metatile_empty(bottom, x, y):
                    layer_attr = 0x0000 
                    encode_layer_secondary(middle, x, y, lookup, lookup_primary, data)
                    encode_layer_secondary(top, x, y, lookup, lookup_primary, data)
                elif is_metatile_empty(middle, x, y):
                    layer_attr = 0x2000
                    encode_layer_secondary(bottom, x, y, lookup, lookup_primary, data)
                    encode_layer_secondary(top, x, y, lookup, lookup_primary, data)
                else:
                    layer_attr = 0x1000
                    encode_layer_secondary(bottom, x, y, lookup, lookup_primary, data)
                    encode_layer_secondary(middle, x, y, lookup, lookup_primary, data)

            # --- Attribute Binary Logic ---
            behavior_name = attributes_list[metatile_index] if metatile_index < len(attributes_list) else "MB_NORMAL"
            behavior_id = BEHAVIOR_MAP.get(behavior_name, 0x00)
            
            final_attribute = behavior_id | layer_attr
            attr_data.extend(struct.pack('<H', final_attribute))
            metatile_index += 1

    return data, attr_data

# ========================
# METATILE BUILD SECONDARY
# ========================

def build_metatiles_bin_secondary(path, unique_img, img_prim, palette_list, palette_list_prim, out_dir, triple_layer=False):
    bottom = Image.open(f"{path}/bottom.png").convert("RGBA")
    middle = Image.open(f"{path}/middle.png").convert("RGBA")
    top = Image.open(f"{path}/top.png").convert("RGBA")

    # Load attributes
    attr_csv_path = os.path.join(path, "attributes.csv")
    attributes_list = []
    if os.path.exists(attr_csv_path):
        with open(attr_csv_path, "r") as f:
            reader = csv.reader(f)
            next(reader, None) 
            for row in reader:
                if len(row) >= 2: attributes_list.append(row[1].strip())

    # Generate lookups
    # Secondary tiles usually start at VRAM index 512
    lookup = get_tile_lookup(unique_img, palette_list, offset=512)
    # Primary tiles start at 0
    lookup_primary = get_tile_lookup(img_prim, palette_list_prim, offset=0)
    
    # Process layers using the new functional logic
    data, attr_data = process_metatile_layers_secondary(
        bottom, middle, top, 
        lookup, lookup_primary, 
        attributes_list, 
        triple_layer=triple_layer
    )

    # Save outputs
    with open(os.path.join(out_dir, "metatiles.bin"), "wb") as f:
        f.write(data)
    with open(os.path.join(out_dir, "metatile_attributes.bin"), "wb") as f:
        f.write(attr_data)

    print(f"Successfully generated secondary metatiles.bin and metatile_attributes.bin")