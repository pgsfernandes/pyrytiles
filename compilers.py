import os
from solver import solve, solve_secondary
from pal_tiles import build_palettes, export_jasc, export_indexed_image
from metatiles import build_metatiles_bin

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

        img, tiles, assignment = result

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(out_dir+"/palettes", exist_ok=True)

        palettes = build_palettes(tiles, assignment)

        export_jasc(palettes, out_dir+"/palettes",False)
        export_indexed_image(img, assignment, palettes, out_dir)
        #build_metatiles_bin(path, img, assignment, out_dir)