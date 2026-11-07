"""Build MapLibre SDF glyph ranges (public/basemap/fonts/<font>/<start>-<end>.pbf) for the basemap label fonts.

OpenFreeMap's glyph server has only Noto, and MapLibre symbol text needs SDF glyphs, so the design fonts are rendered
here: Libre Caslon Text (place names; italic for water) and Barlow Semi Condensed (roads). Fonts are OFL, from
github.com/google/fonts. Same format and parameters as fontnik / sdf-glyph-foundry: 24 px em, 3 px buffer, radius 8,
cutoff 0.25 (so the glyph edge sits at 192, where MapLibre's shader expects it). Each glyph is rendered at 4x and the
distance field is sampled down, which keeps curves clean at label sizes.

Run: .venv/bin/python glyphs.py   (writes ~30 small files; they are committed so labels work without a rebuild)
"""
import os
import struct

import freetype
import httpx
import numpy as np
from scipy.ndimage import distance_transform_edt

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache", "fonts")
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "public", "basemap", "fonts"))
GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {
    "Libre Caslon Text Regular": "librecaslontext/LibreCaslonText%5Bwght%5D.ttf",
    "Libre Caslon Text Italic": "librecaslontext/LibreCaslonText-Italic%5Bwght%5D.ttf",
    "Barlow Semi Condensed Medium": "barlowsemicondensed/BarlowSemiCondensed-Medium.ttf",
}
RANGES = [0, 256, 8192]          # Basic Latin + Latin-1, Latin Extended-A (Baltic and Nordic names), punctuation
EM, BUF, RADIUS, CUTOFF, SS = 24, 3, 8, 0.25, 4


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def field(num, wire, payload):
    key = varint((num << 3) | wire)
    if wire == 0:
        return key + varint(payload)
    return key + varint(len(payload)) + payload


def zigzag(n):
    return (n << 1) ^ (n >> 31)


def sdf(face_hi, face_lo, code):
    """(bitmap bytes, width, height, left, top, advance) at 24 px, or None when the font lacks the glyph."""
    if face_lo.get_char_index(code) == 0:
        return None
    face_lo.load_char(code, freetype.FT_LOAD_DEFAULT | freetype.FT_LOAD_NO_HINTING)
    g = face_lo.glyph
    w, h = g.bitmap.width, g.bitmap.rows
    left, top, adv = g.bitmap_left, g.bitmap_top, round(g.advance.x / 64)
    if w == 0 or h == 0:
        return b"", 0, 0, left, top, adv
    face_hi.load_char(code, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
    gh = face_hi.glyph
    bm = np.array(gh.bitmap.buffer, dtype=np.uint8).reshape(gh.bitmap.rows, gh.bitmap.width) if gh.bitmap.rows else np.zeros((0, 0), np.uint8)
    W, H = (w + 2 * BUF) * SS, (h + 2 * BUF) * SS
    canvas = np.zeros((H, W), np.uint8)
    ox, oy = gh.bitmap_left - (left - BUF) * SS, (top + BUF) * SS - gh.bitmap_top
    y0, x0 = max(0, oy), max(0, ox)
    y1, x1 = min(H, oy + bm.shape[0]), min(W, ox + bm.shape[1])
    if y1 > y0 and x1 > x0:
        canvas[y0:y1, x0:x1] = bm[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    inside = canvas > 127
    d = (distance_transform_edt(~inside) - distance_transform_edt(inside)) / SS   # px at 24 px, + outside
    d = d[SS // 2::SS, SS // 2::SS][: h + 2 * BUF, : w + 2 * BUF]
    v = np.clip(np.round(255 - 255 * (d / RADIUS + CUTOFF)), 0, 255).astype(np.uint8)
    return v.tobytes(), w, h, left, top, adv


def font_path(name, rel):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, os.path.basename(rel).replace("%5B", "[").replace("%5D", "]"))
    if not os.path.exists(p):
        r = httpx.get(GF + rel, timeout=60, follow_redirects=True)
        r.raise_for_status()
        open(p, "wb").write(r.content)
    return p


def main():
    for name, rel in FONTS.items():
        path = font_path(name, rel)
        hi, lo = freetype.Face(path), freetype.Face(path)
        hi.set_pixel_sizes(0, EM * SS)
        lo.set_pixel_sizes(0, EM)
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        for start in range(0, 65536, 256):
            end = start + 255
            glyphs = b""
            if start in RANGES:
                for code in range(start, end + 1):
                    r = sdf(hi, lo, code)
                    if r is None:
                        continue
                    bmp, w, h, left, top, adv = r
                    gl = field(1, 0, code) + (field(2, 2, bmp) if bmp else b"") + field(3, 0, w) + field(4, 0, h) \
                        + field(5, 0, zigzag(left)) + field(6, 0, zigzag(top)) + field(7, 0, adv)
                    glyphs += field(3, 2, gl)
            elif start > max(RANGES):
                break
            stack = field(1, 2, name.encode()) + field(2, 2, f"{start}-{end}".encode()) + glyphs
            open(os.path.join(d, f"{start}-{end}.pbf"), "wb").write(field(1, 2, stack))
        print(name, "done", flush=True)


if __name__ == "__main__":
    main()
