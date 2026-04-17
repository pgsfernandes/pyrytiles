import os
import struct
import csv
import glob
from PIL import Image, ImageOps
from config import BEHAVIOR_MAP, TILE_SIZE, METATILE_SIZE

# ==========================================
# CONFIGURATION
# ==========================================
ORIGINAL_CANVAS_WIDTH = 128 
BEHAVIOR_MAP_REV = {v: k for k, v in BEHAVIOR_MAP.items()}

# ==========================================
# PALETTE HANDLING
# ==========================================
def load_jasc_pal_as_list(filepath):
    """Returns a flattened list [R, G, B...] forcing index 0 to GBA Magenta."""
    colors = []
    with open(filepath, 'r') as f:
        lines = f.readlines()
        color_entries = lines[3:]
        
        for i, line in enumerate(color_entries):
            parts = line.split()
            if len(parts) >= 3:
                if i == 0:
                    # Force first color to GBA Magenta
                    colors.extend([248, 0, 248])
                else:
                    # Use raw colors from file
                    colors.extend([int(parts[0]), int(parts[1]), int(parts[2])])
                    
    while len(colors) < 768:
        colors.extend([0, 0, 0])
    return colors[:768]

def get_paletted_tilesets(tiles_png_path, palettes_dir):
    """Creates a dictionary of {pal_id: RGBA_image} with transparency applied."""
    base_img = Image.open(tiles_png_path).convert("P")
    tileset_versions = {}
    
    pal_files = glob.glob(os.path.join(palettes_dir, "*.pal"))
    for pf in pal_files:
        try:
            pal_id = int(os.path.basename(pf).split('.')[0])
            pal_data = load_jasc_pal_as_list(pf)
            
            # Apply palette to the indexed image
            version = base_img.copy()
            version.putpalette(pal_data)
            
            # Convert to RGBA
            rgba_version = version.convert("RGBA")
            
            # Process pixels to make GBA Magenta (248, 0, 248) transparent
            pixels = rgba_version.getdata()
            new_pixels = []
            for p in pixels:
                if p[0] == 248 and p[1] == 0 and p[2] == 248:
                    new_pixels.append((248, 0, 248, 0)) # Transparent
                else:
                    new_pixels.append(p)
            
            rgba_version.putdata(new_pixels)
            tileset_versions[pal_id] = rgba_version
        except (ValueError, IndexError):
            continue
            
    return tileset_versions

# ==========================================
# CORE DECOMPILER
# ==========================================
def decompile_primary(folder_path, out_dir):
    if not os.path.exists(out_dir): os.makedirs(out_dir)

    # 1. Pre-generate all tileset versions
    print("Pre-generating paletted tilesets...")
    tileset_versions = get_paletted_tilesets(
        os.path.join(folder_path, "tiles.png"),
        os.path.join(folder_path, "palettes")
    )

    # 2. Read Binary Data
    with open(os.path.join(folder_path, "metatiles.bin"), "rb") as f:
        metatile_pixel_data = f.read()
    with open(os.path.join(folder_path, "metatile_attributes.bin"), "rb") as f:
        attr_data = f.read()

    num_metatiles = len(attr_data) // 2
    mt_width_count = ORIGINAL_CANVAS_WIDTH // METATILE_SIZE
    mt_height_count = (num_metatiles + mt_width_count - 1) // mt_width_count
    
    img_w, img_h = mt_width_count * METATILE_SIZE, mt_height_count * METATILE_SIZE
    
    # Transparency logic: grab color 0 from palette 0 as the 'magenta' transparent key
    transparent_bg = (248, 0, 248, 255)
    
    layers = {
        "bottom": Image.new("RGBA", (img_w, img_h), transparent_bg),
        "middle": Image.new("RGBA", (img_w, img_h), transparent_bg),
        "top":    Image.new("RGBA", (img_w, img_h), transparent_bg)
    }
    
    csv_rows = [["id", "behavior"]]

    # 3. Process Metatiles
    for i in range(num_metatiles):
        attr_val = struct.unpack_from("<H", attr_data, i * 2)[0]
        layer_logic = (attr_val & 0xF000)
        behavior_id = (attr_val & 0x00FF)
        csv_rows.append([i, BEHAVIOR_MAP_REV.get(behavior_id, f"0x{behavior_id:02X}")])

        # Layer determination logic
        if layer_logic == 0x0000: target_layers = ["middle", "top"]
        elif layer_logic == 0x2000: target_layers = ["bottom", "top"]
        else: target_layers = ["bottom", "middle"]

        mx, my = (i % mt_width_count) * METATILE_SIZE, (i // mt_width_count) * METATILE_SIZE

        for layer_idx, layer_name in enumerate(target_layers):
            base_offset = (i * 8 + layer_idx * 4) * 2
            
            for t in range(4):
                tile_val = struct.unpack_from("<H", metatile_pixel_data, base_offset + (t * 2))[0]
                
                idx = tile_val & 0x3FF
                h_flip = (tile_val >> 10) & 1
                v_flip = (tile_val >> 11) & 1
                pal_id = (tile_val >> 12) & 0xF
                
                if pal_id in tileset_versions:
                    source_img = tileset_versions[pal_id]
                    
                    # Calculate tile crop from the specific paletted tileset
                    tx = (idx % (source_img.width // TILE_SIZE)) * TILE_SIZE
                    ty = (idx // (source_img.width // TILE_SIZE)) * TILE_SIZE
                    
                    tile_img = source_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
                    
                    if h_flip: tile_img = ImageOps.mirror(tile_img)
                    if v_flip: tile_img = ImageOps.flip(tile_img)
                    
                    dx, dy = (t % 2) * 8, (t // 2) * 8
                    # We use the tile as its own mask to preserve transparency
                    layers[layer_name].paste(tile_img, (mx + dx, my + dy), tile_img)

    # 4. Save
    for name, img in layers.items():
        img.save(os.path.join(out_dir, f"{name}.png"))
    
    with open(os.path.join(out_dir, "attributes.csv"), "w", newline='') as f:
        csv.writer(f).writerows(csv_rows)

    print(f"Successfully decompiled to {out_dir}")


def decompile_secondary(primary_path, secondary_path, out_dir):
    """
    Decompiles a secondary tileset, pulling primary tiles for indices < 512
    and enforcing a minimum output size of 128x1024.
    """
    if not os.path.exists(out_dir): os.makedirs(out_dir)

    # 1. Load both tileset libraries
    print("Loading Primary and Secondary tilesets...")
    primary_paletted = get_paletted_tilesets(
        os.path.join(primary_path, "tiles.png"),
        os.path.join(primary_path, "palettes")
    )
    secondary_paletted = get_paletted_tilesets(
        os.path.join(secondary_path, "tiles.png"),
        os.path.join(secondary_path, "palettes")
    )

    # Merge palettes (Secondary overrides Primary if IDs overlap)
    combined_pals = {**primary_paletted, **secondary_paletted}

    # 2. Read Secondary Binaries
    with open(os.path.join(secondary_path, "metatiles.bin"), "rb") as f:
        metatile_pixel_data = f.read()
    with open(os.path.join(secondary_path, "metatile_attributes.bin"), "rb") as f:
        attr_data = f.read()

    num_metatiles = len(attr_data) // 2
    
    # 3. Calculate Canvas Size (Force at least 128x1024)
    MIN_WIDTH = 128
    MIN_HEIGHT = 1024
    
    mt_width_count = ORIGINAL_CANVAS_WIDTH // METATILE_SIZE
    # Calculate height needed for the actual metatiles
    calculated_height = ((num_metatiles + mt_width_count - 1) // mt_width_count) * METATILE_SIZE
    
    img_w = max(ORIGINAL_CANVAS_WIDTH, MIN_WIDTH)
    img_h = max(calculated_height, MIN_HEIGHT)
    
    magenta_bg = (248, 0, 248, 255)
    layers = {
        "bottom": Image.new("RGBA", (img_w, img_h), magenta_bg),
        "middle": Image.new("RGBA", (img_w, img_h), magenta_bg),
        "top":    Image.new("RGBA", (img_w, img_h), magenta_bg)
    }
    
    csv_rows = [["id", "behavior"]]

    # 4. Process Metatiles
    SECONDARY_TILE_OFFSET = 512

    for i in range(num_metatiles):
        attr_val = struct.unpack_from("<H", attr_data, i * 2)[0]
        layer_logic = (attr_val & 0xF000)
        behavior_id = (attr_val & 0x00FF)
        csv_rows.append([i, BEHAVIOR_MAP_REV.get(behavior_id, f"0x{behavior_id:02X}")])

        if layer_logic == 0x0000: target_layers = ["middle", "top"]
        elif layer_logic == 0x2000: target_layers = ["bottom", "top"]
        else: target_layers = ["bottom", "middle"]

        mx, my = (i % mt_width_count) * METATILE_SIZE, (i // mt_width_count) * METATILE_SIZE

        for layer_idx, layer_name in enumerate(target_layers):
            base_offset = (i * 8 + layer_idx * 4) * 2
            
            for t in range(4):
                tile_val = struct.unpack_from("<H", metatile_pixel_data, base_offset + (t * 2))[0]
                idx = tile_val & 0x3FF
                h_flip = (tile_val >> 10) & 1
                v_flip = (tile_val >> 11) & 1
                pal_id = (tile_val >> 12) & 0xF
                
                # Determine which tileset source to use
                if idx < SECONDARY_TILE_OFFSET:
                    # Use Primary: requires pal_id from combined, but pixels from primary
                    source_lib = primary_paletted
                    tile_idx = idx
                else:
                    # Use Secondary: requires pal_id from combined, but pixels from secondary
                    source_lib = secondary_paletted
                    tile_idx = idx - SECONDARY_TILE_OFFSET

                # Only proceed if we have a valid tileset for this palette
                if pal_id in source_lib:
                    source_img = source_lib[pal_id]
                    tiles_in_row = source_img.width // TILE_SIZE
                    
                    tx = (tile_idx % tiles_in_row) * TILE_SIZE
                    ty = (tile_idx // tiles_in_row) * TILE_SIZE
                    
                    try:
                        tile_img = source_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
                        if h_flip: tile_img = ImageOps.mirror(tile_img)
                        if v_flip: tile_img = ImageOps.flip(tile_img)
                        
                        dx, dy = (t % 2) * 8, (t // 2) * 8
                        layers[layer_name].paste(tile_img, (mx + dx, my + dy), tile_img)
                    except:
                        pass

    # 5. Export
    for name, img in layers.items():
        img.save(os.path.join(out_dir, f"{name}.png"))
    
    with open(os.path.join(out_dir, "attributes.csv"), "w", newline='') as f:
        csv.writer(f).writerows(csv_rows)

    print(f"Decompiled secondary set to {img_w}x{img_h} images.")

decompile_secondary("decompiletest3","decompiletestsec","decompiletestsec/output")