"""Generate the test-label attack set for the TTB verification prototype.

Programmatically rendered (Pillow) rather than AI-generated on purpose: the
government warning is 60 words of statutory text that image-generation models
reliably garble, and a precision test set needs exact, known ground truth.
Each label varies exactly ONE thing from the canonical application data, so a
wrong verdict points at a specific check.

Usage:  python generate.py          (writes PNGs next to this script)
"""
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent
F = "/usr/share/fonts/truetype/dejavu/"

SERIF_B = lambda s: ImageFont.truetype(F + "DejaVuSerif-Bold.ttf", s)
SERIF = lambda s: ImageFont.truetype(F + "DejaVuSerif.ttf", s)
SANS = lambda s: ImageFont.truetype(F + "DejaVuSans.ttf", s)
SANS_B = lambda s: ImageFont.truetype(F + "DejaVuSans-Bold.ttf", s)

CREAM, INK, GOLD = (245, 239, 224), (43, 30, 18), (146, 104, 32)

# Statutory text, 27 CFR 16.21 — must match backend/app/matching.py verbatim.
WARNING_HEADER = "GOVERNMENT WARNING:"
WARNING_BODY = (
    "(1) According to the Surgeon General, women should not drink alcoholic "
    "beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a "
    "car or operate machinery, and may cause health problems."
)
REWORDED_BODY = (
    "(1) The Surgeon General advises that women should avoid alcohol while "
    "pregnant due to possible health issues. (2) Drinking alcohol can impair "
    "your ability to drive or operate machinery."
)


def _mixed_wrap(draw, x, y, max_w, header, body, f_head, f_body, line_h):
    """Word-wrap a paragraph whose leading words use a different font."""
    words = [(w, f_head) for w in header.split()] + [(w, f_body) for w in body.split()]
    cx = x
    for word, font in words:
        w = draw.textlength(word + " ", font=font)
        if cx + w > x + max_w:
            cx, y = x, y + line_h
        draw.text((cx, y), word, font=font, fill=INK)
        cx += w
    return y + line_h


def make_label(
    brand="OLD TOM DISTILLERY",
    class_type="Kentucky Straight Bourbon Whiskey",
    abv_line="45% Alc./Vol. (90 Proof)",
    net="750 mL",
    warning_header=WARNING_HEADER,
    warning_body=WARNING_BODY,
    warning_header_bold=True,
    include_warning=True,
):
    W, H = 900, 1150
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # double border + rule lines
    d.rectangle([18, 18, W - 18, H - 18], outline=INK, width=4)
    d.rectangle([34, 34, W - 34, H - 34], outline=GOLD, width=2)

    def center(text, y, font, fill=INK, tracking_caps=False):
        d.text((W / 2, y), text, font=font, fill=fill, anchor="mm")

    # gold diamond ornament (drawn, not a glyph)
    dx, dy = W / 2, 105
    d.polygon([(dx, dy - 18), (dx + 13, dy), (dx, dy + 18), (dx - 13, dy)], outline=GOLD, width=3)
    center("SMALL BATCH \u00b7 EST. 1887", 155, SANS(22), GOLD)

    # flowing layout: y is a cursor, everything stacks
    y = 240
    for line in textwrap.wrap(brand, width=14):
        center(line, y, SERIF_B(64))
        y += 80
    y += 8
    d.line([W / 2 - 180, y, W / 2 + 180, y], fill=GOLD, width=3)
    y += 52

    for line in textwrap.wrap(class_type, width=26):
        center(line, y, SERIF(36))
        y += 48

    # proof roundel
    cy = y + 105
    d.ellipse([W / 2 - 80, cy - 80, W / 2 + 80, cy + 80], outline=INK, width=4)
    center("AGED", cy - 40, SANS(18))
    center("4", cy, SERIF_B(54))
    center("YEARS", cy + 42, SANS(18))
    y = cy + 125

    center(abv_line, y, SANS_B(30)); y += 46
    center(net, y, SANS(28)); y += 54
    center("DISTILLED AND BOTTLED BY OLD TOM DISTILLERY CO.", y, SANS(17)); y += 28
    center("LOUISVILLE, KENTUCKY", y, SANS(17)); y += 36

    if include_warning:
        d.line([60, y, W - 60, y], fill=INK, width=2)
        f_head = SANS_B(17) if warning_header_bold else SANS(17)
        _mixed_wrap(d, 60, y + 18, W - 120, warning_header, warning_body, f_head, SANS(17), 26)

    return img


def photo_effects(img, angle=-7, glare=True, blur=1.1):
    """Simulate Jenny's bad-photo case: tilt, glare hotspot, slight blur."""
    img = img.rotate(angle, expand=True, fillcolor=(74, 66, 58), resample=Image.BICUBIC)
    if glare:
        overlay = Image.new("L", img.size, 0)
        od = ImageDraw.Draw(overlay)
        gx, gy, r = int(img.width * 0.72), int(img.height * 0.22), 340
        for i in range(r, 0, -4):
            od.ellipse([gx - i, gy - i * 0.7, gx + i, gy + i * 0.7], fill=int(185 * (1 - i / r)))
        img = Image.composite(Image.new("RGB", img.size, (255, 255, 252)), img, overlay)
    return img.filter(ImageFilter.GaussianBlur(blur))


LABELS = {
    # filename: (kwargs, expected verdict)
    "01_clean_pass.png": ({}, "APPROVED"),
    "02_brand_title_case.png": ({"brand": "Old Tom Distillery"}, "APPROVED (match with case note — Dave's scenario)"),
    "03_net_contents_75cl.png": ({"net": "75 cl"}, "APPROVED (equivalent-volume note)"),
    "04_warning_title_case.png": (
        {"warning_header": "Government Warning:"},
        "REJECTED (header not all caps — Jenny's real case)",
    ),
    "05_warning_reworded.png": ({"warning_body": REWORDED_BODY}, "REJECTED (not statutory wording)"),
    "06_abv_mismatch.png": ({"abv_line": "43% Alc./Vol. (86 Proof)"}, "REJECTED (application says 45%)"),
    "07_warning_missing.png": ({"include_warning": False}, "REJECTED (warning missing)"),
}

if __name__ == "__main__":
    for name, (kwargs, _) in LABELS.items():
        make_label(**kwargs).save(OUT / name)
    photo_effects(make_label()).save(OUT / "08_angled_glare.png")
    print(f"Wrote {len(LABELS) + 1} labels to {OUT}")
