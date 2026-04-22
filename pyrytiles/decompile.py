import os
import struct
import csv
import glob
import shutil
from PIL import Image, ImageOps
from .config import BEHAVIOR_MAP, TILE_SIZE, METATILE_SIZE, LAYERS_HEIGHT, LAYERS_WIDTH, NUM_PALETTES
from .utils import create_tileset_library

# ==========================================
# CONFIGURATION
# ==========================================
BEHAVIOR_MAP_REV = {v: k for k, v in BEHAVIOR_MAP.items()}
SECONDARY_TILE_OFFSET = 512

# ==========================================
# PALETTE HANDLING
# ==========================================
def load_jasc_pal_as_list(filepath):
    colors = []
    with open(filepath, 'r') as f:
        lines = f.readlines()[3:]
        for i, line in enumerate(lines):
            parts = line.split()
            if len(parts) >= 3:
                if i == 0:
                    colors.extend([255, 0, 255])
                else:
                    colors.extend([int(parts[0]), int(parts[1]), int(parts[2])])
    while len(colors) < 768:
        colors.extend([0, 0, 0])
    return colors[:768]

def load_palettes(path):
    pals = {}
    for pf in glob.glob(os.path.join(path, "palettes", "*.pal")):
        try:
            pal_id = int(os.path.basename(pf).split('.')[0])
            pals[pal_id] = load_jasc_pal_as_list(pf)
        except ValueError:
            continue
    return pals

def merge_palettes(primary, secondary=None):
    if not secondary:
        return primary

    merged = primary.copy()
    for pal_id, pal_data in secondary.items():
        if pal_id >= NUM_PALETTES or pal_id not in merged:
            merged[pal_id] = pal_data
    return merged

# ==========================================
# UNIFIED DECOMPILER
# ==========================================
def decompile_tileset(primary_path=None, secondary_path=None, out_dir="output", to_print=True, triple_layer=False):
    if not primary_path and not secondary_path:
        raise ValueError("You must provide at least one tileset path.")

    if to_print:
        os.makedirs(out_dir, exist_ok=True)

    # ==========================================
    # MODE DETECTION
    # ==========================================
    has_primary = primary_path is not None
    has_secondary = secondary_path is not None

    p_pals = load_palettes(primary_path) if has_primary else {}
    s_pals = load_palettes(secondary_path) if has_secondary else {}

    # Palette logic depends on mode
    if has_primary and has_secondary:
        # true secondary mode (engine accurate)
        merged_pals = merge_palettes(p_pals, s_pals)
    elif has_secondary:
        # standalone secondary → just use its palettes
        merged_pals = s_pals
    else:
        # primary only
        merged_pals = p_pals

    primary_lib = None
    secondary_lib = None

    if has_primary:
        primary_lib = create_tileset_library(
            os.path.join(primary_path, "tiles.png"),
            merged_pals
        )

    if has_secondary:
        secondary_lib = create_tileset_library(
            os.path.join(secondary_path, "tiles.png"),
            merged_pals
        )

    # Which binary set to read
    bin_path = secondary_path if has_secondary else primary_path

    with open(os.path.join(bin_path, "metatiles.bin"), "rb") as f:
        metatile_pixel_data = f.read()
    with open(os.path.join(bin_path, "metatile_attributes.bin"), "rb") as f:
        attr_data = f.read()

    bytes_per_metatile = 24 if triple_layer else 16

    num_metatiles = len(attr_data) // 2
    mt_per_row = LAYERS_WIDTH // METATILE_SIZE
    img_w = LAYERS_WIDTH
    #img_h = ((num_metatiles + mt_per_row - 1) // mt_per_row) * METATILE_SIZE
    img_h = LAYERS_HEIGHT

    magenta_bg = (255, 0, 255, 255)
    layers = {
        "bottom": Image.new("RGBA", (img_w, img_h), magenta_bg),
        "middle": Image.new("RGBA", (img_w, img_h), magenta_bg),
        "top":    Image.new("RGBA", (img_w, img_h), magenta_bg)
    }

    csv_rows = [["id", "behavior"]]

    for i in range(num_metatiles):
        attr_val = struct.unpack_from("<H", attr_data, i * 2)[0]
        behavior_id = (attr_val & 0x0FFF) # Use more bits for behavior in expanded engines

        csv_rows.append([i, BEHAVIOR_MAP_REV.get(behavior_id & 0xFF, f"0x{behavior_id:02X}")])

        mx = (i % mt_per_row) * METATILE_SIZE
        my = (i // mt_per_row) * METATILE_SIZE

        # --- LAYER MAPPING LOGIC ---
        if triple_layer:
            # Every metatile has all three layers in order
            layer_configs = [
                ("bottom", 0), # Name, Tile Offset (0-3)
                ("middle", 4), # Name, Tile Offset (4-7)
                ("top",    8)  # Name, Tile Offset (8-11)
            ]
        else:
            # Legacy Dual Layer Logic
            layer_logic = (attr_val & 0xF000)
            if layer_logic == 0x0000:
                layer_configs = [("middle", 0), ("top", 4)]
            elif layer_logic == 0x2000:
                layer_configs = [("bottom", 0), ("top", 4)]
            else:
                layer_configs = [("bottom", 0), ("middle", 4)]

        for layer_name, tile_start in layer_configs:
            # base_offset calculation:
            # i * bytes_per_metatile gets us to the start of the current metatile
            # tile_start * 2 gets us to the specific layer within that metatile
            base_offset = (i * bytes_per_metatile) + (tile_start * 2)

            for t in range(4):
                # Ensure we don't read past the end of the file
                if base_offset + (t * 2) + 1 >= len(metatile_pixel_data):
                    continue

                tile_val = struct.unpack_from("<H", metatile_pixel_data, base_offset + (t * 2))[0]

                idx = tile_val & 0x3FF
                h_flip = (tile_val >> 10) & 1
                v_flip = (tile_val >> 11) & 1
                pal_id = (tile_val >> 12) & 0xF

                # ==========================================
                # TILE SOURCE SELECTION (FIXED)
                # ==========================================

                if has_primary and has_secondary:
                    # true engine behavior
                    if idx >= SECONDARY_TILE_OFFSET:
                        source_img = secondary_lib.get(pal_id)
                        tile_idx = idx - SECONDARY_TILE_OFFSET
                    else:
                        source_img = primary_lib.get(pal_id)
                        tile_idx = idx
                elif has_secondary:
                    # standalone secondary -> no split
                    source_img = secondary_lib.get(pal_id)
                    tile_idx = idx
                else:
                    # primary only
                    source_img = primary_lib.get(pal_id)
                    tile_idx = idx

                if source_img is None: continue
                tiles_in_row = source_img.width // TILE_SIZE
                #tx, ty = (idx % tiles_in_row) * TILE_SIZE, (idx // tiles_in_row) * TILE_SIZE
                tx, ty = (tile_idx % tiles_in_row) * TILE_SIZE, (tile_idx // tiles_in_row) * TILE_SIZE
                
                try:
                    tile_img = source_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))
                    if h_flip: tile_img = ImageOps.mirror(tile_img)
                    if v_flip: tile_img = ImageOps.flip(tile_img)

                    dx = (t % 2) * TILE_SIZE
                    dy = (t // 2) * TILE_SIZE
                    layers[layer_name].paste(tile_img, (mx + dx, my + dy), tile_img)
                except:
                    pass
    if to_print:
        for name, img in layers.items():
            img.save(os.path.join(out_dir, f"{name}.png"))

        with open(os.path.join(out_dir, "attributes.csv"), "w", newline='') as f:
            csv.writer(f).writerows(csv_rows)

        anim_src_base = secondary_path if secondary_path else primary_path
        anim_src_path = os.path.join(anim_src_base, "anim")
        
        if os.path.isdir(anim_src_path):
            anim_out_path = os.path.join(out_dir, "anim")
            
            # Copy the entire directory structure
            if os.path.exists(anim_out_path):
                shutil.rmtree(anim_out_path)
            shutil.copytree(anim_src_path, anim_out_path)
            
            # Process copied images to un-index (transform to RGB/RGBA)
            for root, dirs, files in os.walk(anim_out_path):
                for file in files:
                    if file.lower().endswith(".png"):
                        file_path = os.path.join(root, file)
                        with Image.open(file_path) as anim_img:
                            # Convert to RGBA to ensure transparency is preserved 
                            # while stripping the palette (un-indexing)
                            rgb_anim = anim_img.convert("RGBA")
                            rgb_anim.save(file_path)

        print(f"Decompiled to {out_dir}")
    else:
        images=[]
        for name, img in layers.items():
            images.append(img)
        return images