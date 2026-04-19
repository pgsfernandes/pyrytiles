import os
from solver import solve, solve_secondary
from pal_tiles import build_palettes, export_jasc, export_indexed_image, export_indexed_image_secondary
from metatiles import build_metatiles_bin
from config import MAGENTA

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

        export_jasc(palettes, out_dir+"/palettes",False)
        export_indexed_image_secondary(img, full_assignment, join_palettes(palettes,pals_primary), out_dir)
        build_metatiles_bin(path, img, full_assignment, out_dir)