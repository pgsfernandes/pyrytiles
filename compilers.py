import os
from solver import solve
from solver_sec import solve_secondary
from pal_tiles import build_palettes, export_jasc, export_indexed_image
from metatiles import build_metatiles_bin, build_metatiles_bin_secondary
from PIL import Image
from decompile import decompile_tileset
from image_loader import load_tiles_from_imgs
from utils import match_palettes_by_tiles, join_palettes

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

def compile_secondary(path, out_dir, path_primary=None, optimal=False):
    if path_primary is None:
        compile_primary(path,out_dir,optimal,False)
    else:
        result = solve_secondary(path, path_primary, optimal)
        if result is None:
            return

        img, tiles, assignment, full_assignment, pals_primary = result

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(out_dir+"/palettes", exist_ok=True)

        palettes = build_palettes(tiles, assignment)
        
        joined_palettes=join_palettes(palettes,pals_primary)
        tiles_prim=Image.open(path_primary+"/tiles.png")

        export_jasc(palettes, out_dir+"/palettes",False)
        export_indexed_image(img, full_assignment, joined_palettes, out_dir)
        img_prim = load_tiles_from_imgs(decompile_tileset(path_primary,to_print=False))
        build_metatiles_bin_secondary(path, img, img_prim, full_assignment, match_palettes_by_tiles(img_prim,tiles_prim,pals_primary), out_dir)