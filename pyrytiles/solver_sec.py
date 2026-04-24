from ortools.sat.python import cp_model
from .config import TILE_SIZE
from .tiles_secondary import load_tiles_sec, create_output_image
from .utils import load_jasc_pals_from_dir
from .solver import solver_aux
from .shift_tiles_anim import process_image_shift
import sys

class FirstSolutionSelector(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)

    def on_solution_callback(self):
        # This is called the instant a feasible solution is found
        self.StopSearch()

def find_unmatched_tiles(tile_color_sets: list, palettes: dict) -> list:
    """
    Returns the color sets of tiles that don't fit into any single palette.

    :param tile_color_sets: list of sets of (R, G, B) tuples, one per tile
    :param palettes: dict mapping palette_id -> set/list of (R, G, B) tuples
    :return: list of sets of (R, G, B) tuples, same format as input
    """
    unmatched = []

    for tile_colors in tile_color_sets:
        for pal_colors in palettes.values():
            if tile_colors.issubset(set(pal_colors)):
                break
        else:
            unmatched.append(tile_colors)

    return unmatched

def reorder_tiles(tiles_before: list, unmatched: list, assignment: list, pals_primary: dict) -> tuple:
    """
    Reorders tiles so matched ones come first, then unmatched.
    Also returns a full assignment vector for all tiles in the new order.

    :param tiles_before: original full list of tile color sets
    :param unmatched: list of color sets that didn't match any primary palette
    :param assignment: assignment vector for unmatched tiles (indices into secondary palettes)
    :param pals_primary: dict of primary palettes
    :return: (reordered_tile_color_sets, full_assignment)
    """
    unmatched_set = [frozenset(t) for t in unmatched]

    matched = []
    matched_assignments = []

    for tile in tiles_before:
        if frozenset(tile) not in unmatched_set:
            # find which primary palette it fits
            for pal_id, pal_colors in pals_primary.items():
                if set(tile).issubset(set(pal_colors)):
                    matched.append(tile)
                    matched_assignments.append(pal_id)
                    break

    # offset unmatched assignment indices to come after primary palettes
    num_primary = len(pals_primary)
    unmatched_assignments = [a + num_primary for a in assignment]

    reordered_tiles = matched + list(unmatched)
    full_assignment = matched_assignments + unmatched_assignments

    return reordered_tiles, full_assignment

def reorder_image(img, reordered_tiles, tiles_before):
    """
    Creates a new image with tiles in the reordered order (matched first, then unmatched).

    :param img: original PIL image from load_tiles_sec
    :param reordered_tiles: reordered list of tile color sets (matched + unmatched)
    :param tiles_before: original list of tile color sets (same order as img)
    :return: new PIL image with tiles in reordered order
    """
    tiles_per_row = 128 // TILE_SIZE

    # Extract all tile images from the original image, in original order
    tile_images = []
    for idx in range(len(tiles_before)):
        x = (idx % tiles_per_row) * TILE_SIZE
        y = (idx // tiles_per_row) * TILE_SIZE
        tile_img = img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
        tile_images.append((frozenset(tiles_before[idx]), tile_img))

    # Build a lookup from color set -> tile image
    # Use a list to handle duplicates (multiple tiles with same color set)
    from collections import defaultdict
    lookup = defaultdict(list)
    for color_set, tile_img in tile_images:
        lookup[color_set].append(tile_img)

    # Track how many times each color set has been used
    usage = defaultdict(int)

    # Build reordered tile images
    reordered_tile_images = []
    for tile_colors in reordered_tiles:
        key = frozenset(tile_colors)
        idx = usage[key]
        reordered_tile_images.append(lookup[key][idx])
        usage[key] += 1

    return create_output_image(reordered_tile_images)

def optimize_palette_slots(unmatched_tiles, palettes, max_swaps):
    """
    Finds the best (palette, color) combinations to fill (0,0,0) slots.
    """
    # Check if any empty slots exist anywhere before starting
    all_colors = [c for colors in palettes.values() for c in colors]
    if (0, 0, 0) not in all_colors:
        print("Error: No empty slots (0,0,0) found in any palette.")
        sys.exit()

    working_pals = {pid: set(colors) for pid, colors in palettes.items()}
    swaps_made = 0
    
    while swaps_made < max_swaps and unmatched_tiles:
        best_gain = -1
        best_pick = None # (palette_id, color)

        # 1. Identify all unique colors currently causing tiles to be unmatched
        candidate_colors = set()
        for tile in unmatched_tiles:
            candidate_colors.update(tile)
        
        # 2. Evaluate every palette that has at least one (0,0,0) slot
        for pid, pal_set in working_pals.items():
            # Check empty slots for this specific palette
            if (0, 0, 0) not in palettes[pid]:
                continue
            
            for color in candidate_colors:
                if color in pal_set:
                    continue
                
                # HYPOTHETICAL: What if we add this color to THIS palette?
                test_pal = pal_set | {color}
                
                # How many tiles does this specific addition "rescue"?
                rescued_count = 0
                for tile in unmatched_tiles:
                    if tile.issubset(test_pal):
                        rescued_count += 1
                
                if rescued_count > best_gain:
                    best_gain = rescued_count
                    best_pick = (pid, color)

        # 3. If we found a move that actually helps, apply it
        if best_pick and best_gain > 0:
            pid, color = best_pick
            working_pals[pid].add(color)
            
            # Update the actual palettes structure (replace first 0,0,0 found)
            for i, c in enumerate(palettes[pid]):
                if c == (0, 0, 0):
                    palettes[pid][i] = color
                    break
            
            #unmatched_tiles = find_unmatched_tiles(unmatched_tiles, working_pals)
            
            swaps_made += 1
            print(f"Swap {swaps_made}: Added {color} to Palette {pid} (Rescued {best_gain} tiles)")
        else:
            # If we reach here, no single color addition completes a tile.
            print("No further single-color rescues possible.")
            break

    return palettes

def solve_secondary(path, path_primary, optimal, number_optimization=0):
    img, tiles, primary_library = load_tiles_sec(path, path_primary)

    pals_primary=load_jasc_pals_from_dir(path_primary+"/palettes")
    unmatched = find_unmatched_tiles(tiles, pals_primary)

    if number_optimization>0:
        pals_primary = optimize_palette_slots(unmatched,pals_primary,number_optimization)
        unmatched = find_unmatched_tiles(tiles, pals_primary)

    print("Number of unique secondary tiles that cannot use primary palettes: ", len(unmatched))

    # Update the reference
    tiles_before=tiles
    tiles=unmatched
    n = len(tiles)

    assignment = solver_aux(n,tiles,optimal)
    if assignment is None:
        return None

    reordered_tiles, full_assignment = reorder_tiles(tiles_before, tiles, assignment, pals_primary)
    img_new = reorder_image(img, reordered_tiles,tiles_before)

    img_new_2, full_assignment_2, reordered_tiles_2 = process_image_shift(img_new,path,full_assignment,reordered_tiles)

    return img_new_2, full_assignment_2, pals_primary, reordered_tiles_2, primary_library