import os
from PIL import Image
from .solver import solve
from .solver_sec import solve_secondary
from .pal_tiles import build_palettes, export_jasc, export_indexed_image, index_image_from_master, export_anims
from .metatiles import build_metatiles_bin, build_metatiles_bin_secondary
from .decompile import decompile_tileset
from .image_loader import load_tiles_from_imgs
from .utils import match_palettes_by_tiles, join_palettes, get_palette_indices_from_indexed
from .shift_tiles_anim import process_image_shift

def compile_primary(path, out_dir, optimal=False, is_primary=True, triple_layer=False):
    result = solve(path, optimal)
    if result is None:
        return

    #img_old, tiles_old, assignment_old = result
    img, tiles, assignment = result
    #img, tiles, assignment = process_image_shift(img_old,path,assignment_old, tiles_old)

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir+"/palettes", exist_ok=True)

    palettes = build_palettes(tiles, assignment)

    export_jasc(palettes, out_dir+"/palettes",is_primary)
    indexed_tiles_img=export_indexed_image(img, assignment, palettes, out_dir)

    export_anims(path,out_dir,indexed_tiles_img)

    build_metatiles_bin(path, img, assignment, out_dir, triple_layer)

def compile_secondary(path, out_dir, path_primary=None, optimal=False, triple_layer=False):
    if path_primary is None:
        compile_primary(path,out_dir,optimal,is_primary=False)
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
        #img_prim = load_tiles_from_imgs(decompile_tileset(path_primary,to_print=False,triple_layer=triple_layer))
        #img_prim = Image.open(path_primary+"/tiles.png").convert("RGBA")
        #img_prim = process_image_shift(load_tiles_from_imgs(decompile_tileset(path_primary,to_print=False,triple_layer=triple_layer)),path_primary)
        #build_metatiles_bin_secondary(path, img, img_prim, full_assignment, match_palettes_by_tiles(img_prim,tiles_prim,pals_primary), out_dir, triple_layer=triple_layer)
        build_metatiles_bin_secondary(path, img, tiles_prim.convert("RGBA"), full_assignment, get_palette_indices_from_indexed(tiles_prim), out_dir, triple_layer=triple_layer)