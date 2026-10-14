
from collections import Counter
from pathlib import Path
import pymupdf

pdf_path = Path("data/source/Ward 178 Final.pdf")
doc = pymupdf.open(pdf_path)
page = doc[0]
drawings = page.get_drawings()

print("Total drawing objects:", len(drawings))
print("Page size:", page.rect)

styles = Counter()
regions = Counter()
item_types = Counter()

page_width = page.rect.width
page_height = page.rect.height

for drawing in drawings:
    color = drawing.get("color")
    width = round(drawing.get("width") or 0, 3)
    styles[(str(color), width)] += 1

    # Divide the page into a 3-by-3 grid for summary only.
    rect = drawing.get("rect")
    if rect:
        x = min(2, max(0, int(3 * rect.x0 / page_width)))
        y = min(2, max(0, int(3 * rect.y0 / page_height)))
        regions[(x, y)] += 1

    for item in drawing.get("items", []):
        if item:
            item_types[str(item[0])] += 1

print("\nMost common stroke colors and widths:")
for (color, width), count in styles.most_common(20):
    print(f"Color={color}, width={width}: {count}")

print("\nDrawing item types:")
for item_type, count in item_types.most_common():
    print(f"{item_type}: {count}")

print("\nDrawing objects by page region:")
for y in range(3):
    print("  ".join(
        f"{regions.get((x, y), 0):7d}" for x in range(3)
    ))

print("\nAnalysis complete. No geometry was exported.")
