#!/usr/bin/env python3
"""Shaded preview of the SIZE-01 mockups -> hardware/packets/size-01/preview.png

    python3 preview.py

A tiny depth-buffered rasterizer, because matplotlib's 3-D painter's sort
draws big flat faces in the wrong order. Picture only -- the gates live in
mockups.py.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mockups as M

def tris(part, color, tol=0.1):
    v, f = M.whole(part)[1].tessellate(tol, 0.2)
    v = np.array([(p.x, p.y, p.z) for p in v]); T = v[np.array(f)]
    return T, np.tile(matplotlib.colors.to_rgb(color), (len(T), 1))

def rot(elev, azim):
    a, e = np.radians(azim), np.radians(elev)
    Rz = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(e), -np.sin(e)], [0, np.sin(e), np.cos(e)]])
    return Rx @ Rz   # camera looks down -z after rotation

def render(groups, elev, azim, size=520):
    T = np.vstack([g[0] for g in groups]); C = np.vstack([g[1] for g in groups])
    R = rot(-(90 - elev), azim)
    P = T @ R.T
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    n /= np.linalg.norm(n, axis=1)[:, None] + 1e-12
    L = np.array([-0.4, 0.5, 0.75]); L /= np.linalg.norm(L)
    shade = 0.28 + 0.72 * np.abs(n @ L)
    lo, hi = P.reshape(-1, 3).min(0), P.reshape(-1, 3).max(0)
    s = (size - 20) / max(hi[0] - lo[0], hi[1] - lo[1])
    xy = (P[:, :, :2] - lo[:2]) * s + 10
    xy[:, :, 1] = size - xy[:, :, 1]
    z = P[:, :, 2]
    img = np.ones((size, size, 3)); zb = np.full((size, size), -np.inf)
    for t in range(len(P)):
        (x0, y0), (x1, y1), (x2, y2) = xy[t]
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-9: continue
        xa, xb = int(max(0, np.floor(min(x0, x1, x2)))), int(min(size - 1, np.ceil(max(x0, x1, x2))))
        ya, yb = int(max(0, np.floor(min(y0, y1, y2)))), int(min(size - 1, np.ceil(max(y0, y1, y2))))
        if xa > xb or ya > yb: continue
        X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        a = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / d
        b = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / d
        c = 1 - a - b
        m = (a >= -1e-6) & (b >= -1e-6) & (c >= -1e-6)
        if not m.any(): continue
        zz = a * z[t, 0] + b * z[t, 1] + c * z[t, 2]
        sub = zb[ya:yb + 1, xa:xb + 1]
        w = m & (zz > sub)
        sub[w] = zz[w]
        img[ya:yb + 1, xa:xb + 1][w] = C[t] * shade[t]
    return img

w, o = M.wm2(), M.ours()
G, B = "#c9c9c9", "#7fa3cf"
views = [
 ("WM-2 closed: controls face (lid, blue)", [tris(w["tray"], G), tris(w["lid"], B)], 50, 20),
 ("WM-2 closed: door face (tray, grey)", [tris(w["tray"], G), tris(w["lid"], B)], -50, 200),
 ("WM-2 open: tray, tongue, coin grid", [tris(w["tray"], G)], 60, 200),
 ("Ours closed: front + top-edge keys", [tris(o["tray"], G), tris(o["lid"], B)], 40, 200),
 ("Ours closed: back, thumbwheel, jack side", [tris(o["tray"], G), tris(o["lid"], B)], -40, 130),
 ("Ours open: tray, tongue, coin grid", [tris(o["tray"], G)], 60, 200),
]
fig, axs = plt.subplots(2, 3, figsize=(15, 10.5))
for ax, (t, g, e, a) in zip(axs.flat, views):
    ax.imshow(render(g, e, a)); ax.set_title(t, fontsize=11); ax.axis("off")
plt.tight_layout()
plt.savefig(sys.argv[1] if len(sys.argv) > 1 else M.OUT / "preview.png", dpi=100)
