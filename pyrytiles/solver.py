from ortools.sat.python import cp_model
from .config import NUM_PALETTES, MAX_COLORS, MAX_TIME
from .image_loader import load_tiles

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
        print("No solution exists.")
        return None
    
    if status == cp_model.OPTIMAL:
        print("Solution found and is optimal!")
    elif status == cp_model.FEASIBLE:
        print("Solution found!")

    assignment = [
        next(p for p in range(NUM_PALETTES) if solver.Value(x[t, p]))
        for t in range(n)
    ]
    return img, tiles, assignment