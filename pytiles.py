import os
import struct
from collections import defaultdict

from ortools.sat.python import cp_model
from PIL import Image, ImageOps

import tiles_dedup


# ========================
# CONFIG
# ========================
TILE_SIZE = 8
METATILE_SIZE = 16

NUM_PALETTES = 6
MAX_COLORS = 15

MAGENTA = (255, 0, 255)

MAX_TIME = 100.0


# ========================
# COLOR UTILS
# ========================
def to_gba(color):
    r, g, b = color[:3]
    return ((r // 8) * 8, (g // 8) * 8, (b // 8) * 8)


def color_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def nearest_palette_index(color, palette):
    best_idx, best_dist = 1, float("inf")

    for i, pc in enumerate(palette):
        dist = color_distance(color, pc)
        if dist < best_dist:
            best_idx, best_dist = i, dist

    return best_idx


# ========================
# TILE LOADING
# ========================
def load_tiles(path):
    input_paths = [f"{path}/{layer}.png" for layer in ("bottom", "middle", "top")]
    output_path = f"{path}/unique_tiles.png"

    img, _ = tiles_dedup.dedup(input_paths, output_path, False)
    img = img.convert("RGBA")

    tiles = []
    w, h = img.size

    for ty in range(0, h, TILE_SIZE):
        for tx in range(0, w, TILE_SIZE):
            colors = {
                to_gba(img.getpixel((tx + x, ty + y))[:3])
                for y in range(TILE_SIZE)
                for x in range(TILE_SIZE)
                if img.getpixel((tx + x, ty + y))[3] != 0
            }

            colors.discard(to_gba(MAGENTA))
            tiles.append(colors)

    return img, tiles


# ========================
# SOLVER
# ========================
class FirstSolutionSelector(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)

    def on_solution_callback(self):
        # This is called the instant a feasible solution is found
        self.StopSearch()

def solve(path, optimal):
    img, tiles = load_tiles(path)
    n = len(tiles)

    model = cp_model.CpModel()

    x = {
        (t, p): model.NewBoolVar(f"x_{t}_{p}")
        for t in range(n)
        for p in range(NUM_PALETTES)
    }

    # each tile → one palette
    for t in range(n):
        model.Add(sum(x[t, p] for p in range(NUM_PALETTES)) == 1)

    colors = sorted({c for tile in tiles for c in tile})

    used = {
        (p, c): model.NewBoolVar(f"u_{p}_{hash(c)}")
        for p in range(NUM_PALETTES)
        for c in colors
    }

    for p in range(NUM_PALETTES):
        for c in colors:
            tiles_with_c = [t for t in range(n) if c in tiles[t]]

            if tiles_with_c:
                model.AddMaxEquality(used[p, c], [x[t, p] for t in tiles_with_c])
            else:
                model.Add(used[p, c] == 0)

        model.Add(sum(used[p, c] for c in colors) <= MAX_COLORS)

    model.Minimize(sum(used.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = MAX_TIME
    print("Looking for a solution...")
    if optimal:
        status = solver.Solve(model)
    else:
        solution_callback = FirstSolutionSelector()
        status = solver.Solve(model, solution_callback)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No solution found")
        return None

    assignment = [
        next(p for p in range(NUM_PALETTES) if solver.Value(x[t, p]))
        for t in range(n)
    ]

    print("Solution found!")
    return img, tiles, assignment


# ========================
# PALETTE BUILDING
# ========================
def build_palettes(tiles, assignment):
    palettes = defaultdict(set)

    for tile, p in zip(tiles, assignment):
        palettes[p] |= tile

    final = []

    for p in range(NUM_PALETTES):
        colors = [to_gba(c) for c in list(palettes[p])[:MAX_COLORS]]

        palette = [to_gba(MAGENTA)] + colors
        palette += [(0, 0, 0)] * (16 - len(palette))

        final.append(palette)

    return final


# ========================
# EXPORT PALETTE
# ========================
def export_jasc(palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    for i, pal in enumerate(palettes):
        filename = f"{i:02d}.pal"
        with open(os.path.join(out_dir, filename), "w") as f:
            f.write("JASC-PAL\n0100\n16\n")
            for r, g, b in pal:
                f.write(f"{r} {g} {b}\n")

    print("Palettes exported")


# ========================
# IMAGE EXPORT
# ========================
def build_pil_palette(palette):
    flat = [v for color in palette for v in color]
    flat += [0] * (256 * 3 - len(flat))
    return flat


def export_indexed_image(img, assignment, palettes, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    w, h = img.size
    tiles_x = w // TILE_SIZE
    gba_magenta = to_gba(MAGENTA)

    best_palette = max(
        palettes,
        key=lambda p: sum(1 for i, c in enumerate(p) if i and c != (0, 0, 0))
    )

    composite = Image.new("P", (w, h))
    composite.putpalette(build_pil_palette(best_palette))

    for i, assigned_p in enumerate(assignment):
        palette = palettes[assigned_p]

        tx = (i % tiles_x) * TILE_SIZE
        ty = (i // tiles_x) * TILE_SIZE

        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                raw = to_gba(img.getpixel((tx + x, ty + y)))

                idx = 0 if raw == gba_magenta else nearest_palette_index(raw, palette)
                composite.putpixel((tx + x, ty + y), idx)

    composite.save(os.path.join(out_dir, "tiles.png"), bits=4)


# ========================
# METATILE HELPERS
# ========================
def is_metatile_empty(img, x, y):
    mag = (248, 0, 248)
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
import os
import struct
import csv
from PIL import Image

# 1. Define the mapping based on your enum
# You can expand this dictionary with all the MB_ constants you need
BEHAVIOR_MAP = {
    "MB_NORMAL": 0x00,
    "MB_SECRET_BASE_WALL": 0x01,
    "MB_TALL_GRASS": 0x02,
    "MB_LONG_GRASS": 0x03,
    "MB_UNUSED_04": 0x04,
    "MB_UNUSED_05": 0x05,
    "MB_DEEP_SAND": 0x06,
    "MB_SHORT_GRASS": 0x07,
    "MB_CAVE": 0x08,
    "MB_LONG_GRASS_SOUTH_EDGE": 0x09,
    "MB_NO_RUNNING": 0x0A,
    "MB_INDOOR_ENCOUNTER": 0x0B,
    "MB_MOUNTAIN_TOP": 0x0C,
    "MB_BATTLE_PYRAMID_WARP": 0x0D,
    "MB_MOSSDEEP_GYM_WARP": 0x0E,
    "MB_MT_PYRE_HOLE": 0x0F,
    "MB_POND_WATER": 0x10,
    "MB_INTERIOR_DEEP_WATER": 0x11,
    "MB_DEEP_WATER": 0x12,
    "MB_WATERFALL": 0x13,
    "MB_SOOTOPOLIS_DEEP_WATER": 0x14,
    "MB_OCEAN_WATER": 0x15,
    "MB_PUDDLE": 0x16,
    "MB_SHALLOW_WATER": 0x17,
    "MB_UNUSED_SOOTOPOLIS_DEEP_WATER": 0x18,
    "MB_NO_SURFACING": 0x19,
    "MB_UNUSED_SOOTOPOLIS_DEEP_WATER_2": 0x1A,
    "MB_STAIRS_OUTSIDE_ABANDONED_SHIP": 0x1B,
    "MB_SHOAL_CAVE_ENTRANCE": 0x1C,
    "MB_SIGNPOST": 0x1D,
    "MB_POKEMON_CENTER_SIGN": 0x1E,
    "MB_POKEMART_SIGN": 0x1F,
    "MB_ICE": 0x20,
    "MB_SAND": 0x21,
    "MB_SEAWEED": 0x22,
    "MB_UNUSED_23": 0x23,
    "MB_ASHGRASS": 0x24,
    "MB_FOOTPRINTS": 0x25,
    "MB_THIN_ICE": 0x26,
    "MB_CRACKED_ICE": 0x27,
    "MB_HOT_SPRINGS": 0x28,
    "MB_LAVARIDGE_GYM_B1F_WARP": 0x29,
    "MB_SEAWEED_NO_SURFACING": 0x2A,
    "MB_REFLECTION_UNDER_BRIDGE": 0x2B,
    "MB_UNUSED_2C": 0x2C,
    "MB_UNUSED_2D": 0x2D,
    "MB_UNUSED_2E": 0x2E,
    "MB_UNUSED_2F": 0x2F,
    "MB_IMPASSABLE_EAST": 0x30,
    "MB_IMPASSABLE_WEST": 0x31,
    "MB_IMPASSABLE_NORTH": 0x32,
    "MB_IMPASSABLE_SOUTH": 0x33,
    "MB_IMPASSABLE_NORTHEAST": 0x34,
    "MB_IMPASSABLE_NORTHWEST": 0x35,
    "MB_IMPASSABLE_SOUTHEAST": 0x36,
    "MB_IMPASSABLE_SOUTHWEST": 0x37,
    "MB_JUMP_EAST": 0x38,
    "MB_JUMP_WEST": 0x39,
    "MB_JUMP_NORTH": 0x3A,
    "MB_JUMP_SOUTH": 0x3B,
    "MB_JUMP_NORTHEAST": 0x3C,
    "MB_JUMP_NORTHWEST": 0x3D,
    "MB_JUMP_SOUTHEAST": 0x3E,
    "MB_JUMP_SOUTHWEST": 0x3F,
    "MB_WALK_EAST": 0x40,
    "MB_WALK_WEST": 0x41,
    "MB_WALK_NORTH": 0x42,
    "MB_WALK_SOUTH": 0x43,
    "MB_SLIDE_EAST": 0x44,
    "MB_SLIDE_WEST": 0x45,
    "MB_SLIDE_NORTH": 0x46,
    "MB_SLIDE_SOUTH": 0x47,
    "MB_TRICK_HOUSE_PUZZLE_8_FLOOR": 0x48,
    "MB_SIDEWAYS_STAIRS_RIGHT_SIDE": 0x49,
    "MB_SIDEWAYS_STAIRS_LEFT_SIDE": 0x4A,
    "MB_SIDEWAYS_STAIRS_RIGHT_SIDE_TOP": 0x4B,
    "MB_SIDEWAYS_STAIRS_LEFT_SIDE_TOP": 0x4C,
    "MB_SIDEWAYS_STAIRS_RIGHT_SIDE_BOTTOM": 0x4D,
    "MB_SIDEWAYS_STAIRS_LEFT_SIDE_BOTTOM": 0x4E,
    "MB_ROCK_STAIRS": 0x4F,
    "MB_EASTWARD_CURRENT": 0x50,
    "MB_WESTWARD_CURRENT": 0x51,
    "MB_NORTHWARD_CURRENT": 0x52,
    "MB_SOUTHWARD_CURRENT": 0x53,
    "MB_UNUSED_54": 0x54,
    "MB_UNUSED_55": 0x55,
    "MB_UNUSED_56": 0x56,
    "MB_UNUSED_57": 0x57,
    "MB_UNUSED_58": 0x58,
    "MB_UNUSED_59": 0x59,
    "MB_UNUSED_5A": 0x5A,
    "MB_UNUSED_5B": 0x5B,
    "MB_UNUSED_5C": 0x5C,
    "MB_UNUSED_5D": 0x5D,
    "MB_UNUSED_5E": 0x5E,
    "MB_UNUSED_5F": 0x5F,
    "MB_NON_ANIMATED_DOOR": 0x60,
    "MB_LADDER": 0x61,
    "MB_EAST_ARROW_WARP": 0x62,
    "MB_WEST_ARROW_WARP": 0x63,
    "MB_NORTH_ARROW_WARP": 0x64,
    "MB_SOUTH_ARROW_WARP": 0x65,
    "MB_CRACKED_FLOOR_HOLE": 0x66,
    "MB_AQUA_HIDEOUT_WARP": 0x67,
    "MB_LAVARIDGE_GYM_1F_WARP": 0x68,
    "MB_ANIMATED_DOOR": 0x69,
    "MB_UP_ESCALATOR": 0x6A,
    "MB_DOWN_ESCALATOR": 0x6B,
    "MB_WATER_DOOR": 0x6C,
    "MB_WATER_SOUTH_ARROW_WARP": 0x6D,
    "MB_DEEP_SOUTH_WARP": 0x6E,
    "MB_UNUSED_6F": 0x6F,
    "MB_BRIDGE_OVER_OCEAN": 0x70,
    "MB_BRIDGE_OVER_POND_LOW": 0x71,
    "MB_BRIDGE_OVER_POND_MED": 0x72,
    "MB_BRIDGE_OVER_POND_HIGH": 0x73,
    "MB_PACIFIDLOG_VERTICAL_LOG_TOP": 0x74,
    "MB_PACIFIDLOG_VERTICAL_LOG_BOTTOM": 0x75,
    "MB_PACIFIDLOG_HORIZONTAL_LOG_LEFT": 0x76,
    "MB_PACIFIDLOG_HORIZONTAL_LOG_RIGHT": 0x77,
    "MB_FORTREE_BRIDGE": 0x78,
    "MB_UNUSED_79": 0x79,
    "MB_BRIDGE_OVER_POND_MED_EDGE_1": 0x7A,
    "MB_BRIDGE_OVER_POND_MED_EDGE_2": 0x7B,
    "MB_BRIDGE_OVER_POND_HIGH_EDGE_1": 0x7C,
    "MB_BRIDGE_OVER_POND_HIGH_EDGE_2": 0x7D,
    "MB_UNUSED_BRIDGE": 0x7E,
    "MB_BIKE_BRIDGE_OVER_BARRIER": 0x7F,
    "MB_COUNTER": 0x80,
    "MB_UNUSED_81": 0x81,
    "MB_UNUSED_82": 0x82,
    "MB_PC": 0x83,
    "MB_CABLE_BOX_RESULTS_1": 0x84,
    "MB_REGION_MAP": 0x85,
    "MB_TELEVISION": 0x86,
    "MB_POKEBLOCK_FEEDER": 0x87,
    "MB_UNUSED_88": 0x88,
    "MB_SLOT_MACHINE": 0x89,
    "MB_ROULETTE": 0x8A,
    "MB_CLOSED_SOOTOPOLIS_DOOR": 0x8B,
    "MB_TRICK_HOUSE_PUZZLE_DOOR": 0x8C,
    "MB_PETALBURG_GYM_DOOR": 0x8D,
    "MB_RUNNING_SHOES_INSTRUCTION": 0x8E,
    "MB_QUESTIONNAIRE": 0x8F,
    "MB_SECRET_BASE_SPOT_RED_CAVE": 0x90,
    "MB_SECRET_BASE_SPOT_RED_CAVE_OPEN": 0x91,
    "MB_SECRET_BASE_SPOT_BROWN_CAVE": 0x92,
    "MB_SECRET_BASE_SPOT_BROWN_CAVE_OPEN": 0x93,
    "MB_SECRET_BASE_SPOT_YELLOW_CAVE": 0x94,
    "MB_SECRET_BASE_SPOT_YELLOW_CAVE_OPEN": 0x95,
    "MB_SECRET_BASE_SPOT_TREE_LEFT": 0x96,
    "MB_SECRET_BASE_SPOT_TREE_LEFT_OPEN": 0x97,
    "MB_SECRET_BASE_SPOT_SHRUB": 0x98,
    "MB_SECRET_BASE_SPOT_SHRUB_OPEN": 0x99,
    "MB_SECRET_BASE_SPOT_BLUE_CAVE": 0x9A,
    "MB_SECRET_BASE_SPOT_BLUE_CAVE_OPEN": 0x9B,
    "MB_SECRET_BASE_SPOT_TREE_RIGHT": 0x9C,
    "MB_SECRET_BASE_SPOT_TREE_RIGHT_OPEN": 0x9D,
    "MB_UNUSED_9E": 0x9E,
    "MB_UNUSED_9F": 0x9F,
    "MB_BERRY_TREE_SOIL": 0xA0,
    "MB_UNUSED_A1": 0xA1,
    "MB_UNUSED_A2": 0xA2,
    "MB_UNUSED_A3": 0xA3,
    "MB_UNUSED_A4": 0xA4,
    "MB_UNUSED_A5": 0xA5,
    "MB_UNUSED_A6": 0xA6,
    "MB_UNUSED_A7": 0xA7,
    "MB_UNUSED_A8": 0xA8,
    "MB_UNUSED_A9": 0xA9,
    "MB_UNUSED_AA": 0xAA,
    "MB_UNUSED_AB": 0xAB,
    "MB_UNUSED_AC": 0xAC,
    "MB_UNUSED_AD": 0xAD,
    "MB_UNUSED_AE": 0xAE,
    "MB_UNUSED_AF": 0xAF,
    "MB_SECRET_BASE_PC": 0xB0,
    "MB_SECRET_BASE_REGISTER_PC": 0xB1,
    "MB_SECRET_BASE_SCENERY": 0xB2,
    "MB_SECRET_BASE_TRAINER_SPOT": 0xB3,
    "MB_SECRET_BASE_DECORATION": 0xB4,
    "MB_HOLDS_SMALL_DECORATION": 0xB5,
    "MB_UNUSED_B6": 0xB6,
    "MB_SECRET_BASE_NORTH_WALL": 0xB7,
    "MB_SECRET_BASE_BALLOON": 0xB8,
    "MB_SECRET_BASE_IMPASSABLE": 0xB9,
    "MB_SECRET_BASE_GLITTER_MAT": 0xBA,
    "MB_SECRET_BASE_JUMP_MAT": 0xBB,
    "MB_SECRET_BASE_SPIN_MAT": 0xBC,
    "MB_SECRET_BASE_SOUND_MAT": 0xBD,
    "MB_SECRET_BASE_BREAKABLE_DOOR": 0xBE,
    "MB_SECRET_BASE_SAND_ORNAMENT": 0xBF,
    "MB_IMPASSABLE_SOUTH_AND_NORTH": 0xC0,
    "MB_IMPASSABLE_WEST_AND_EAST": 0xC1,
    "MB_SECRET_BASE_HOLE": 0xC2,
    "MB_HOLDS_LARGE_DECORATION": 0xC3,
    "MB_SECRET_BASE_TV_SHIELD": 0xC4,
    "MB_PLAYER_ROOM_PC_ON": 0xC5,
    "MB_SECRET_BASE_DECORATION_BASE": 0xC6,
    "MB_SECRET_BASE_POSTER": 0xC7,
    "MB_UNUSED_C8": 0xC8,
    "MB_UNUSED_C9": 0xC9,
    "MB_UNUSED_CA": 0xCA,
    "MB_UNUSED_CB": 0xCB,
    "MB_UNUSED_CC": 0xCC,
    "MB_UNUSED_CD": 0xCD,
    "MB_UNUSED_CE": 0xCE,
    "MB_UNUSED_CF": 0xCF,
    "MB_MUDDY_SLOPE": 0xD0,
    "MB_BUMPY_SLOPE": 0xD1,
    "MB_CRACKED_FLOOR": 0xD2,
    "MB_ISOLATED_VERTICAL_RAIL": 0xD3,
    "MB_ISOLATED_HORIZONTAL_RAIL": 0xD4,
    "MB_VERTICAL_RAIL": 0xD5,
    "MB_HORIZONTAL_RAIL": 0xD6,
    "MB_UNUSED_D7": 0xD7,
    "MB_UNUSED_D8": 0xD8,
    "MB_UNUSED_D9": 0xD9,
    "MB_UNUSED_DA": 0xDA,
    "MB_UNUSED_DB": 0xDB,
    "MB_UNUSED_DC": 0xDC,
    "MB_UNUSED_DD": 0xDD,
    "MB_UNUSED_DE": 0xDE,
    "MB_UNUSED_DF": 0xDF,
    "MB_PICTURE_BOOK_SHELF": 0xE0,
    "MB_BOOKSHELF": 0xE1,
    "MB_POKEMON_CENTER_BOOKSHELF": 0xE2,
    "MB_VASE": 0xE3,
    "MB_TRASH_CAN": 0xE4,
    "MB_SHOP_SHELF": 0xE5,
    "MB_BLUEPRINT": 0xE6,
    "MB_CABLE_BOX_RESULTS_2": 0xE7,
    "MB_WIRELESS_BOX_RESULTS": 0xE8,
    "MB_TRAINER_HILL_TIMER": 0xE9,
    "MB_SKY_PILLAR_CLOSED_DOOR": 0xEA,
    "MB_UP_RIGHT_STAIR_WARP": 0xEB,
    "MB_UP_LEFT_STAIR_WARP": 0xEC,
    "MB_DOWN_RIGHT_STAIR_WARP": 0xED,
    "MB_DOWN_LEFT_STAIR_WARP": 0xEE,
    "MB_ROCK_CLIMB": 0xEF,
    "MB_INVALID": 0xFF
}

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

# ========================
# MAIN
# ========================
def compile_primary(path, out_dir, optimal=False):
    result = solve(path, optimal)
    if result is None:
        return

    img, tiles, assignment = result

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir+"/palettes", exist_ok=True)

    palettes = build_palettes(tiles, assignment)

    export_jasc(palettes, out_dir+"/palettes")
    export_indexed_image(img, assignment, palettes, out_dir)
    build_metatiles_bin(path, img, assignment, out_dir)

#compile_primary("lightplat","lightplat_output",60.0)
#compile_primary("emerald","$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary",1.0)

input_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/emerald")
out_dir = os.path.expandvars("$HOME/Documents/pkmndecomps/pokeemerald-expansion/data/tilesets/primary/test_primary")
compile_primary(input_dir,out_dir,True)