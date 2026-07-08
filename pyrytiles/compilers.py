import os
from PIL import Image
from .solver import solve
from .solver_sec import solve_secondary
from .pal_tiles import build_palettes, export_jasc, export_indexed_image, export_anims
from .metatiles import build_metatiles_bin, build_metatiles_bin_secondary
from .utils import join_palettes, get_palette_indices_from_indexed
from .config import get_game_profile

def compile_primary(path, out_dir, optimal=False, is_primary=True, triple_layer=False, game="emerald"):
    profile = get_game_profile(game)

    print()
    print("---------------------")

    result = solve(path, optimal, game=game, is_primary=is_primary)
    if result is None:
        return

    img, tiles, assignment = result

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(out_dir+"/palettes", exist_ok=True)

    palette_count = profile["primary_palette_count"] if is_primary else profile["secondary_palette_count"]
    palettes = build_palettes(tiles, assignment, palette_count=palette_count)

    export_jasc(
        palettes,
        out_dir+"/palettes",
        is_primary,
        primary_palette_count=profile["primary_palette_count"],
        secondary_palette_count=profile["secondary_palette_count"],
        total_palette_count=profile["total_palette_count"],
    )
    if is_primary:
        indexed_tiles_img=export_indexed_image(img, assignment, palettes, out_dir)
    else:
        first_color = (255, 0, 255)
        other_colors = (0, 0, 0)
        
        palettes_empty = []
        for _ in range(profile["primary_palette_count"]):
            palette_empty = [first_color] + [other_colors] * 15
            palettes_empty.append(palette_empty)
        indexed_tiles_img=export_indexed_image(
            img,
            [x + profile["primary_palette_count"] for x in assignment],
            palettes_empty + palettes,
            out_dir,
        )

    export_anims(path,out_dir,indexed_tiles_img)

    if is_primary:
        build_metatiles_bin(path, img, assignment, out_dir, triple_layer, is_primary, profile)
    else:
        build_metatiles_bin(
            path,
            img,
            [x + profile["primary_palette_count"] for x in assignment],
            out_dir,
            triple_layer,
            is_primary,
            profile,
        )

    print("---------------------")
    print()

def compile_secondary(path, out_dir, path_primary=None, optimal=False, triple_layer=False, use_primary_palette_empty_slots=False, game="emerald"):
    profile = get_game_profile(game)

    print()
    print("---------------------")

    if path_primary is None:
        compile_primary(path, out_dir, optimal, is_primary=False, triple_layer=triple_layer, game=game)
    else:
        result = solve_secondary(path, path_primary, optimal, game=game)
        if result is None:
            if use_primary_palette_empty_slots:
                n=1
                while result is None:
                    result = solve_secondary(path, path_primary, optimal, n, game=game)
                    n=n+1
            else:
                return
        #if result is None:
        #    return

        img, full_assignment, pals_primary, reordered_tiles, primary_library = result

        if use_primary_palette_empty_slots:
            export_jasc(pals_primary, path_primary+"/palettes",True)

        os.makedirs(out_dir, exist_ok=True)
        os.makedirs(out_dir+"/palettes", exist_ok=True)

        palettes = build_palettes(
            reordered_tiles,
            full_assignment,
            True,
            palette_count=profile["secondary_palette_count"],
            primary_palette_count=profile["primary_palette_count"],
        )
        
        joined_palettes=join_palettes(palettes,pals_primary)

        export_jasc(
            palettes,
            out_dir+"/palettes",
            False,
            primary_palette_count=profile["primary_palette_count"],
            secondary_palette_count=profile["secondary_palette_count"],
            total_palette_count=profile["total_palette_count"],
        )
        indexed_tiles_img = export_indexed_image(img, full_assignment, joined_palettes, out_dir)

        export_anims(path,out_dir,indexed_tiles_img)

        build_metatiles_bin_secondary(path, img, primary_library, full_assignment, out_dir, triple_layer=triple_layer, profile=profile)

    print("---------------------")
    print()
