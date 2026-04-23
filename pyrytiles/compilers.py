import os
from PIL import Image
from .solver import solve
from .solver_sec import solve_secondary
from .pal_tiles import build_palettes, export_jasc, export_indexed_image, export_anims
from .metatiles import build_metatiles_bin, build_metatiles_bin_secondary
from .utils import join_palettes, get_palette_indices_from_indexed

def compile_primary(path, out_dir, optimal=False, is_primary=True, triple_layer=False):

    print()
    print("---------------------")

    result = solve(path, optimal)
    if result is None:
        return

    img, tiles, assignment = result

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir+"/palettes", exist_ok=True)

    palettes = build_palettes(tiles, assignment)

    export_jasc(palettes, out_dir+"/palettes",is_primary)
    indexed_tiles_img=export_indexed_image(img, assignment, palettes, out_dir)

    export_anims(path,out_dir,indexed_tiles_img)

    build_metatiles_bin(path, img, assignment, out_dir, triple_layer)

    print("---------------------")
    print()

def compile_secondary(path, out_dir, path_primary=None, optimal=False, triple_layer=False):
    print()
    print("---------------------")

    if path_primary is None:
        compile_primary(path,out_dir,optimal,is_primary=False)
    else:
        result = solve_secondary(path, path_primary, optimal)
        if result is None:
            return

        img, full_assignment, pals_primary, reordered_tiles, primary_library = result

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(out_dir+"/palettes", exist_ok=True)

        palettes = build_palettes(reordered_tiles, full_assignment, True)
        
        joined_palettes=join_palettes(palettes,pals_primary)

        export_jasc(palettes, out_dir+"/palettes",False)
        indexed_tiles_img = export_indexed_image(img, full_assignment, joined_palettes, out_dir)

        export_anims(path,out_dir,indexed_tiles_img)

        build_metatiles_bin_secondary(path, img, primary_library, full_assignment, out_dir, triple_layer=triple_layer)

    print("---------------------")
    print()