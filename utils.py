def to_gba(color):
    r, g, b = color[:3]
    return ((r // 8) * 8, (g // 8) * 8, (b // 8) * 8)

def color_distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))

def nearest_palette_index(color, palette):
    best_idx, best_dist = 1, float("inf")
    for i, pc in enumerate(palette):
        dist = color_distance(color, pc)
        if dist < best_dist:
            best_idx, best_dist = i, dist
    return best_idx

def from_gba_value(val):
    """
    Reverts (val // 8) * 8 by stretching the 5-bit result 
    back to a full 8-bit 0-255 range.
    """
    five_bit = val // 8
    return (five_bit * 255) // 31