import os
from ortools.sat.python import cp_model
from config import NUM_PALETTES, MAX_COLORS, MAX_TIME, TILE_SIZE
from tiles_secondary import load_tiles_sec, create_output_image
from utils import load_jasc_pals_from_dir

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

def solve_secondary(path, path_primary, optimal):
    img, tiles = load_tiles_sec(path, path_primary)

    pals_primary=load_jasc_pals_from_dir(path_primary+"/palettes")
    unmatched = find_unmatched_tiles(tiles, pals_primary)

    print("Number of unique secondary tiles that cannot use primary palettes: ", len(unmatched))

    # Update the reference
    tiles_before=tiles
    tiles=unmatched
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

    reordered_tiles, full_assignment = reorder_tiles(tiles_before, tiles, assignment, pals_primary)
    img_new = reorder_image(img, reordered_tiles,tiles_before)

    return img_new, tiles, assignment, full_assignment, pals_primary