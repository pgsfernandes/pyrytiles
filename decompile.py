import os
import struct
import csv
import glob
from PIL import Image, ImageOps
from config import BEHAVIOR_MAP, TILE_SIZE, METATILE_SIZE, LAYERS_HEIGHT, LAYERS_WIDTH

# ==========================================
# CONFIGURATION
# ==========================================
ORIGINAL_CANVAS_WIDTH = 128 
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
        if pal_id >= 6 or pal_id not in merged:
            merged[pal_id] = pal_data
    return merged

# ==========================================
# TILESET LIBRARY
# ==========================================
def create_tileset_library(tiles_png_path, palettes):
    if not os.path.exists(tiles_png_path):
        return {}

    base_img = Image.open(tiles_png_path).convert("P")
    library = {}

    for pal_id, pal_data in palettes.items():
        version = base_img.copy()
        version.putpalette(pal_data)
        rgba = version.convert("RGBA")

        indices = list(base_img.getdata())
        pixels = list(rgba.getdata())

        new_pixels = [
            (r, g, b, 0) if indices[i] == 0 else (r, g, b, a)
            for i, (r, g, b, a) in enumerate(pixels)
        ]

        rgba.putdata(new_pixels)
        library[pal_id] = rgba

    return library

def gba_to_8bit_channel(c):
    """Convert 0–248 stepped GBA channel back to full 0–255."""
    v = c >> 3          # back to 5-bit (0–31)
    return (v << 3) | (v >> 2)

def restore_gba_image(img):
    """Apply GBA color expansion to an RGBA image."""
    pixels = list(img.getdata())
    new_pixels = []

    for r, g, b, a in pixels:
        if a == 0:
            new_pixels.append((r, g, b, a))
        else:
            new_pixels.append((
                gba_to_8bit_channel(r),
                gba_to_8bit_channel(g),
                gba_to_8bit_channel(b),
                a
            ))

    img.putdata(new_pixels)
    return img

# ==========================================
# UNIFIED DECOMPILER
# ==========================================
def decompile_tileset(primary_path=None, secondary_path=None, out_dir="output"):
    if not primary_path and not secondary_path:
        raise ValueError("You must provide at least one tileset path.")

    os.makedirs(out_dir, exist_ok=True)

    # ==========================================
    # MODE DETECTION
    # ==========================================
    has_primary = primary_path is not None
    has_secondary = secondary_path is not None

    print("Loading palettes...")

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

    print("Generating tileset libraries...")

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

    num_metatiles = len(attr_data) // 2
    mt_per_row = ORIGINAL_CANVAS_WIDTH // METATILE_SIZE
    img_w = ORIGINAL_CANVAS_WIDTH
    img_h = ((num_metatiles + mt_per_row - 1) // mt_per_row) * METATILE_SIZE

    img_w=LAYERS_WIDTH
    img_h=LAYERS_HEIGHT

    magenta_bg = (255, 0, 255, 255)
    layers = {
        "bottom": Image.new("RGBA", (img_w, img_h), magenta_bg),
        "middle": Image.new("RGBA", (img_w, img_h), magenta_bg),
        "top":    Image.new("RGBA", (img_w, img_h), magenta_bg)
    }

    csv_rows = [["id", "behavior"]]

    for i in range(num_metatiles):
        attr_val = struct.unpack_from("<H", attr_data, i * 2)[0]
        layer_logic = (attr_val & 0xF000)
        behavior_id = (attr_val & 0x00FF)

        csv_rows.append([i, BEHAVIOR_MAP_REV.get(behavior_id, f"0x{behavior_id:02X}")])

        if layer_logic == 0x0000:
            target_layers = ["middle", "top"]
        elif layer_logic == 0x2000:
            target_layers = ["bottom", "top"]
        else:
            target_layers = ["bottom", "middle"]

        mx = (i % mt_per_row) * METATILE_SIZE
        my = (i // mt_per_row) * METATILE_SIZE

        for layer_idx, layer_name in enumerate(target_layers):
            base_offset = (i * 8 + layer_idx * 4) * 2

            for t in range(4):
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
                    # standalone secondary → no split
                    source_img = secondary_lib.get(pal_id)
                    tile_idx = idx
                else:
                    # primary only
                    source_img = primary_lib.get(pal_id)
                    tile_idx = idx

                if source_img is None:
                    continue

                tiles_in_row = source_img.width // TILE_SIZE
                tx = (tile_idx % tiles_in_row) * TILE_SIZE
                ty = (tile_idx // tiles_in_row) * TILE_SIZE

                try:
                    tile_img = source_img.crop((tx, ty, tx + TILE_SIZE, ty + TILE_SIZE))

                    if h_flip:
                        tile_img = ImageOps.mirror(tile_img)
                    if v_flip:
                        tile_img = ImageOps.flip(tile_img)

                    dx = (t % 2) * TILE_SIZE
                    dy = (t // 2) * TILE_SIZE

                    layers[layer_name].paste(tile_img, (mx + dx, my + dy), tile_img)
                except:
                    pass

    for name, img in layers.items():
        img.save(os.path.join(out_dir, f"{name}.png"))

    with open(os.path.join(out_dir, "attributes.csv"), "w", newline='') as f:
        csv.writer(f).writerows(csv_rows)

    print(f"Decompiled to {out_dir}")

# ==========================================
# USAGE
# ==========================================

# Primary only
# decompile_tileset("data/tilesets/primary/xxx")

# Secondary (primary + secondary)
#decompile_tileset("decompiletest3", "decompiletestsec", "decompiletestsec/output")
#decompile_tileset(primary_path="decompiletest3", secondary_path="decompiletestsec2", out_dir="decompiletestsec2/output")
#decompile_tileset(secondary_path="decompiletestsec2", out_dir="decompiletestsec2/output2")
#decompile_tileset(primary_path="decompiletest3", secondary_path="decompiletestsec", out_dir="decompiletestsec/output2")
#decompile_tileset(primary_path="decompiletest", out_dir="decompiletest/output2")