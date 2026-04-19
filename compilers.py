import os
from solver import solve
from solver_sec import solve_secondary
from pal_tiles import build_palettes, export_jasc, export_indexed_image, export_indexed_image_secondary
from metatiles import build_metatiles_bin, build_metatiles_bin_secondary
from PIL import Image
from utils import vconcat_indexed
from config import MAGENTA
from image_loader import load_tiles

def compile_primary(path, out_dir, optimal=False, is_primary=True):
    result = solve(path, optimal)
    if result is None:
        return

    img, tiles, assignment = result

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir+"/palettes", exist_ok=True)

    palettes = build_palettes(tiles, assignment)

    export_jasc(palettes, out_dir+"/palettes",is_primary)
    export_indexed_image(img, assignment, palettes, out_dir)
    build_metatiles_bin(path, img, assignment, out_dir)

from tiles_dedup import split_into_tiles

def get_primary_palette_map(tile_color_sets: list, palettes: dict) -> dict:
    """
    Compares each tile's color set against all palettes.

    :param tile_color_sets: list of sets of (R, G, B) tuples, one per tile
    :param palettes: dict mapping palette_id -> set/list of (R, G, B) tuples
    :return: dict with per-tile results and a summary
    """

    matching_palettes = []

    for i, tile_colors in enumerate(tile_color_sets):

        for pal_id, pal_colors in palettes.items():
            pal_set = set(pal_colors)
            missing = tile_colors - pal_set

            if not missing:
                matching_palettes.append(pal_id)
                break

    return matching_palettes

from decompile import decompile_tileset
from image_loader import load_tiles_from_imgs
from utils import match_palettes_by_tiles

def compile_secondary(path, out_dir, path_primary=None, optimal=False):
    if path_primary is None:
        compile_primary(path,out_dir,optimal,False)
    else:
        result = solve_secondary(path, path_primary, optimal)
        if result is None:
            return

        img, tiles, assignment, full_assignment, pals_primary = result

        #img.save(os.path.join(out_dir, "debug.png"))

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(out_dir+"/palettes", exist_ok=True)

        palettes = build_palettes(tiles, assignment)

        def join_palettes(list_palettes: list, dict_palettes: dict) -> list:
            """
            Prepends dict_palettes to list_palettes, returning a single list of lists.

            :param list_palettes: list of lists of (R, G, B) tuples (e.g. from build_palettes)
            :param dict_palettes: dict mapping int -> set of (R, G, B) tuples (e.g. from load_jasc_pals)
            :return: list of lists of (R, G, B) tuples
            """
            joined = []

            for pal_id in sorted(dict_palettes.keys()):
                joined.append(list(dict_palettes[pal_id]))

            joined.extend(list_palettes)

            return joined
        
        joined_palettes=join_palettes(palettes,pals_primary)
        tiles_prim=Image.open(path_primary+"/tiles.png")

        export_jasc(palettes, out_dir+"/palettes",False)

        tiles_second=export_indexed_image_secondary(img, full_assignment, joined_palettes, out_dir)
        total_tiles=vconcat_indexed(tiles_prim,tiles_second)
        total_tiles.save(os.path.expandvars("$HOME/Documents/pkmndecomps/pyrytiles/debug.png"))

        #def prepend_zeros(v, n):
        #    return [0]*n + v
        
        #full_assignment_with_prim=prepend_zeros(full_assignment,len(split_into_tiles(tiles_prim)))

        imgprim, prim_colors_sets = load_tiles_from_imgs(decompile_tileset(path_primary,to_print=False))

        #print(match_palettes_by_tiles(imgprim,tiles_prim,pals_primary))

        #build_metatiles_bin_secondary(path, img, imgprim, full_assignment, get_primary_palette_map(prim_colors_sets,pals_primary), out_dir)
        build_metatiles_bin_secondary(path, img, imgprim, full_assignment, match_palettes_by_tiles(imgprim,tiles_prim,pals_primary), out_dir)
        #build_metatiles_bin_secondary(path, total_tiles, full_assignment_with_prim, out_dir)