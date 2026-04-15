"""Generate PWA icons for Receipt Reader.

Run after installing Pillow:
    pip install Pillow
    python generate_icons.py
"""

from PIL import Image, ImageDraw
import os

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

for size in [192, 512]:
    img = Image.new("RGBA", (size, size), (248, 240, 255, 255))
    draw = ImageDraw.Draw(img)
    margin = size // 8
    # Purple circle
    draw.ellipse([margin, margin, size - margin, size - margin],
                 fill=(155, 114, 207, 255))
    # White receipt shape
    cx, cy = size // 2, size // 2
    r = size // 4
    draw.rounded_rectangle([cx - r // 2, cy - r, cx + r // 2, cy + r],
                           radius=r // 6, fill=(255, 255, 255, 255))
    # Small lines on the receipt
    lw = max(2, r // 10)
    for i in range(3):
        y = cy - r // 2 + (i + 1) * r // 2
        draw.line([cx - r // 4, y, cx + r // 4, y],
                  fill=(155, 114, 207, 255), width=lw)

    out = os.path.join(STATIC_DIR, f"icon-{size}.png")
    img.save(out)
    print(f"Created {out}")
