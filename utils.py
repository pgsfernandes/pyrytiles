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

from PIL import Image

def vconcat_indexed(img1, img2):
    """
    Vertically concatenate two PIL images in 'P' mode (indexed PNG).
    
    If palettes match → preserves indices exactly.
    If palettes differ → remaps img2 to img1's palette.
    """
    if img1.mode != "P" or img2.mode != "P":
        raise ValueError("Both images must be in 'P' (indexed) mode")

    # Copy to avoid modifying originals
    img1 = img1.copy()
    img2 = img2.copy()

    palette1 = img1.getpalette()
    palette2 = img2.getpalette()

    # If palettes differ, remap img2 to img1's palette
    #if palette1 != palette2:
    #    img2 = img2.quantize(palette=img1)

    # Create output image
    w = max(img1.width, img2.width)
    h = img1.height + img2.height

    out = Image.new("P", (w, h))
    out.putpalette(img1.getpalette())

    # Paste images
    out.paste(img1, (0, 0))
    out.paste(img2, (0, img1.height))

    return out