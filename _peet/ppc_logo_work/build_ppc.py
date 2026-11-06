#!/usr/bin/env python3
"""Build deAutomation-AlternativeData-PPC.png from sibling glyphs, recoloured Peet blue.

Method: extract coverage (alpha) of SGP 'P' and LIC 'C' from their flattest
colour channels, re-ink in Peet Primary #003B5C, lay out P-P-C with 46px
tracking (matches house: SGP span 986px), reuse pixel-identical subtitle band.
"""
from PIL import Image
import os

MEDIA = "/Users/duivesteyn/Library/CloudStorage/GoogleDrive-duivesteyn@gmail.com/My Drive/Documents/Documents Collection/deAutomation Pty Ltd/00 Media/03 AlternativeData"
PEET = (0, 59, 92)          # #003B5C — Peet Primary (theme.json + favicon)
SIZE = 1000

def coverage(im, box, channel, fg):
    """Per-pixel ink coverage 0..1 from one channel: t=(255-v)/(255-fg)."""
    crop = im.crop(box)
    px = crop.load()
    w, h = crop.size
    t = Image.new("L", (w, h))
    tp = t.load()
    denom = 255 - fg
    for y in range(h):
        for x in range(w):
            v = px[x, y][channel]
            a = (255 - v) / denom
            tp[x, y] = 255 if a >= 1 else (0 if a <= 0 else round(a * 255))
    return t

def inked(alpha):
    """White canvas with PEET ink at coverage alpha."""
    out = Image.new("RGB", alpha.size, (255, 255, 255))
    opx = out.load(); apx = alpha.load()
    w, h = alpha.size
    for y in range(h):
        for x in range(w):
            a = apx[x, y] / 255
            if a > 0:
                opx[x, y] = (round(PEET[0]*a + 255*(1-a)),
                             round(PEET[1]*a + 255*(1-a)),
                             round(PEET[2]*a + 255*(1-a)))
    return out

sgp = Image.open(os.path.join(MEDIA, "SGP", "deAutomation-AlternativeData-SGP.png")).convert("RGB")
lic = Image.open(os.path.join(MEDIA, "LIC", "deAutomation-AlternativeData-LIC.png")).convert("RGB")

P = inked(coverage(sgp, (699, 261, 986, 610), 0, 51))    # SGP P, red channel (fg R=51)
C = inked(coverage(lic, (552, 263, 872, 611), 2, 39))    # LIC C, blue channel (fg B=39)
print("P", P.size, "C", C.size)   # expect (287,349) (320,348)

canvas = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
TOP = 261
x = 7
for g in (P, P, C):
    canvas.paste(g, (x, TOP))
    x += g.size[0] + 46
print("ticker ink x: 7..%d" % (x - 46))

sub = sgp.crop((0, 630, SIZE, 760))     # pixel-identical across CWP/SGP/LIC
canvas.paste(sub, (0, 630))

out = os.path.join(MEDIA, "PPC", "deAutomation-AlternativeData-PPC.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
canvas.save(out)
print("wrote", out)
