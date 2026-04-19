from ortools.sat.python import cp_model
from config import NUM_PALETTES, MAX_COLORS, MAX_TIME
from image_loader import load_tiles
from tiles_secondary import load_tiles_sec, load_palettes

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


##
import os

def fits_palette(tile, palette_set):
    return all(c in palette_set for c in tile)

def load_jasc_pal(pal_path: str) -> list:
    """
    Loads a JASC-PAL file and returns its colors as a list of (R, G, B) tuples,
    preserving order.
    """
    with open(pal_path, "r") as f:
        lines = [line.strip() for line in f.readlines()]

    if lines[0] != "JASC-PAL" or lines[1] != "0100":
        raise ValueError(f"Invalid JASC-PAL file: {pal_path}")

    num_colors = int(lines[2])

    colors = []
    for line in lines[3:3 + num_colors]:
        r, g, b = map(int, line.split())
        colors.append((r, g, b))

    return colors
def load_jasc_pals_from_dir(pal_dir: str, max_index: int = 5) -> dict:
    """
    Loads JASC-PAL files from a directory, optionally filtering by index.
    
    :param pal_dir: path to directory containing .pal files
    :param max_index: if set, only loads palettes with numeric index <= max_index
    :return: dict mapping palette filename (without extension) -> set of (R, G, B) tuples
    """
    palettes = {}
    for fname in sorted(os.listdir(pal_dir)):
        if fname.endswith(".pal"):
            pal_id = os.path.splitext(fname)[0]
            if max_index is not None:
                try:
                    if int(pal_id) > max_index:
                        continue
                except ValueError:
                    continue  # skip non-numeric filenames
            palettes[int(pal_id)] = load_jasc_pal(os.path.join(pal_dir, fname))
    return palettes

def compare_tile_colors_to_palettes(tile_color_sets: list, palettes: dict) -> dict:
    """
    Compares each tile's color set against all palettes.

    :param tile_color_sets: list of sets of (R, G, B) tuples, one per tile
    :param palettes: dict mapping palette_id -> set/list of (R, G, B) tuples
    :return: dict with per-tile results and a summary
    """
    results = []

    for i, tile_colors in enumerate(tile_color_sets):
        matching_palettes = []
        best_palette = None
        best_missing = None

        for pal_id, pal_colors in palettes.items():
            pal_set = set(pal_colors)
            missing = tile_colors - pal_set

            if not missing:
                matching_palettes.append(pal_id)
            else:
                if best_missing is None or len(missing) < len(best_missing):
                    best_missing = missing
                    best_palette = pal_id

        fits = len(matching_palettes) > 0
        results.append({
            "tile_index":         i,
            "fits":               fits,
            "matching_palettes":  matching_palettes,
            "closest_palette":    best_palette if not fits else None,
            "missing_colors":     best_missing if not fits else set(),
        })

    total = len(results)
    fitting = sum(1 for r in results if r["fits"])

    summary = {
        "total_tiles":       total,
        "fitting_tiles":     fitting,
        "non_fitting_tiles": total - fitting,
    }

    return {"results": results, "summary": summary}

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

from tiles_secondary import create_output_image

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

from config import TILE_SIZE

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

    #print(load_jasc_pals_from_dir(path_primary+"/palettes"))
    pals_primary=load_jasc_pals_from_dir(path_primary+"/palettes")
    #report = compare_tile_colors_to_palettes(tiles, pals_primary)
    unmatched = find_unmatched_tiles(tiles, pals_primary)
    '''
    for r in report["results"]:
        if r["fits"]:
            print(f"Tile {r['tile_index']}: fits palettes {r['matching_palettes']}")
        #else:
        #    print(f"Tile {r['tile_index']}: no fit — closest: {r['closest_palette']}, missing: {r['missing_colors']}")
    '''

    #print(report["summary"])

    print("Number of tiles to matched to secondary palettes: ", len(unmatched))

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

    #return img, tiles, assignment, pals_primary
    return img_new, tiles, assignment, full_assignment, pals_primary