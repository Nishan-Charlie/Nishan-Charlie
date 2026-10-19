"""Renders a rotating 3D Gaussian splatting scene as animated WebP files.

The scene is a procedural tree with an understory of shrubs on a ground
disc, a nod to LiDAR-based fuel structure work. Every element is an
anisotropic 3D Gaussian (position, covariance, colour, opacity). Each frame
projects the Gaussians to 2D covariances through a perspective camera that
orbits the scene, sorts them by depth and alpha-composites them front to
back, as in 3D Gaussian splatting.

Outputs (transparent background):
  assets/splat-dark.webp   for GitHub dark theme
  assets/splat-light.webp  for GitHub light theme

Usage:  python scripts/splat_tree.py
Needs:  numpy, pillow
"""
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
RNG = np.random.default_rng(11)

SIZE = 320          # output pixels
SS = 2              # supersampling factor
FRAMES = 60
FPS_MS = 70         # ms per frame

PALETTES = {
    # wood, leaf_lo, leaf_hi, ground, accent (understory fuel)
    "dark": dict(wood=(0.55, 0.58, 0.62), leaf_lo=(0.62, 0.66, 0.70), leaf_hi=(0.93, 0.95, 0.97),
                 ground=(0.25, 0.28, 0.32), accent=(0.89, 0.70, 0.25)),
    "light": dict(wood=(0.30, 0.32, 0.35), leaf_lo=(0.22, 0.25, 0.28), leaf_hi=(0.50, 0.54, 0.58),
                  ground=(0.72, 0.75, 0.78), accent=(0.60, 0.40, 0.0)),
}


# ------------------------------------------------------------------ scene
def frame_from(d):
    """Orthonormal basis whose first axis is d."""
    d = d / np.linalg.norm(d)
    a = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d, a); u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return np.stack([d, u, v], axis=1)


def random_rot():
    q = RNG.normal(size=4); q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def build_scene():
    pos, cov, kind, opac = [], [], [], []

    def add(p, R, s, k, o):
        pos.append(p); cov.append(R @ np.diag(np.square(s)) @ R.T); kind.append(k); opac.append(o)

    tips = []

    def branch(start, direction, length, radius, depth):
        end = start + direction * length
        n = max(3, int(length / (radius * 1.2)))
        R = frame_from(direction)
        for i in range(n):
            t = (i + 0.5) / n
            r = radius * (1 - 0.35 * t)
            add(start + direction * length * t + RNG.normal(scale=r * 0.15, size=3), R,
                [length / n * 0.75, r, r], 0, 0.95)
        if depth == 0:
            tips.append(end)
            return
        k = 3 if depth > 1 else RNG.integers(2, 4)
        for _ in range(k):
            nd = direction + RNG.normal(scale=0.55, size=3)
            nd[1] = abs(nd[1]) * 0.8 + 0.25
            nd /= np.linalg.norm(nd)
            branch(end, nd, length * RNG.uniform(0.62, 0.78), radius * 0.62, depth - 1)

    branch(np.array([0.0, -1.0, 0.0]), np.array([0.0, 1.0, 0.0]), 0.75, 0.055, 4)

    # foliage clusters around branch tips
    for tip in tips:
        for _ in range(42):
            p = tip + RNG.normal(scale=0.15, size=3) * np.array([1, 0.75, 1])
            add(p, random_rot(), RNG.uniform(0.008, 0.035, size=3) * np.array([1, 1, 0.3]), 1,
                RNG.uniform(0.55, 0.9))

    # understory shrubs (the "fuel" layer) in the accent colour
    for _ in range(9):
        ang, rad = RNG.uniform(0, 2 * math.pi), RNG.uniform(0.35, 0.95)
        c = np.array([math.cos(ang) * rad, -0.93, math.sin(ang) * rad])
        for _ in range(28):
            p = c + RNG.normal(scale=[0.07, 0.05, 0.07])
            p[1] = max(p[1], -0.99)
            add(p, random_rot(), RNG.uniform(0.012, 0.035, size=3), 2, RNG.uniform(0.6, 0.9))

    # ground disc
    for _ in range(900):
        ang, rad = RNG.uniform(0, 2 * math.pi), 1.15 * math.sqrt(RNG.uniform())
        p = np.array([math.cos(ang) * rad, -1.0 + RNG.normal(scale=0.008), math.sin(ang) * rad])
        add(p, np.eye(3), [0.03, 0.004, 0.03], 3, 0.4 * (1 - rad / 1.3))

    return np.array(pos), np.array(cov), np.array(kind), np.array(opac)


def colours(kind, pos, pal):
    out = np.zeros((len(kind), 3))
    h = (pos[:, 1] + 1) / 2.2
    for i, k in enumerate(kind):
        if k == 0:
            out[i] = np.array(pal["wood"]) * RNG.uniform(0.85, 1.05)
        elif k == 1:
            t = np.clip(h[i] + RNG.normal(scale=0.15), 0, 1)
            out[i] = np.array(pal["leaf_lo"]) * (1 - t) + np.array(pal["leaf_hi"]) * t
        elif k == 2:
            out[i] = np.array(pal["accent"]) * RNG.uniform(0.85, 1.1)
        else:
            out[i] = pal["ground"]
    return np.clip(out, 0, 1)


# ------------------------------------------------------------------ render
def render(pos, cov, col, opa, yaw, pitch=0.32, dist=3.4):
    W = SIZE * SS
    f = W * 0.8
    cy_, sy_ = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Rw = Rx @ Ry
    cam = (pos - np.array([0, -0.1, 0])) @ Rw.T
    z = dist - cam[:, 2]
    u = W / 2 + f * cam[:, 0] / z
    v = W / 2 - f * cam[:, 1] / z
    order = np.argsort(z)            # nearest first, composited front to back

    rgb = np.zeros((W, W, 3))
    T = np.ones((W, W))
    for i in order:
        S = Rw @ cov[i] @ Rw.T
        J = np.array([[f / z[i], 0, 0], [0, -f / z[i], 0]])
        S2 = J @ S @ J.T + np.eye(2) * 0.35
        det = S2[0, 0] * S2[1, 1] - S2[0, 1] ** 2
        inv = np.array([[S2[1, 1], -S2[0, 1]], [-S2[0, 1], S2[0, 0]]]) / det
        rx, ry = 3 * math.sqrt(S2[0, 0]), 3 * math.sqrt(S2[1, 1])
        x0, x1 = int(max(u[i] - rx, 0)), int(min(u[i] + rx + 1, W))
        y0, y1 = int(max(v[i] - ry, 0)), int(min(v[i] + ry + 1, W))
        if x0 >= x1 or y0 >= y1:
            continue
        xs = np.arange(x0, x1) - u[i]
        ys = np.arange(y0, y1) - v[i]
        dx, dy = np.meshgrid(xs, ys)
        q = inv[0, 0] * dx * dx + 2 * inv[0, 1] * dx * dy + inv[1, 1] * dy * dy
        a = np.minimum(0.99, opa[i] * np.exp(-0.5 * q))
        t = T[y0:y1, x0:x1]
        rgb[y0:y1, x0:x1] += (t * a)[..., None] * col[i]
        T[y0:y1, x0:x1] = t * (1 - a)

    alpha = 1 - T
    # un-premultiply for RGBA output
    out_rgb = np.where(alpha[..., None] > 1e-4, rgb / np.maximum(alpha[..., None], 1e-4), 0)
    img = np.dstack([np.clip(out_rgb, 0, 1), alpha])
    im = Image.fromarray((img * 255).astype(np.uint8), "RGBA")
    return im.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    pos, cov, kind, opa = build_scene()
    print(f"{len(pos)} gaussians")
    for mode, pal in PALETTES.items():
        col = colours(kind, pos, pal)
        frames = [render(pos, cov, col, opa, 2 * math.pi * k / FRAMES) for k in range(FRAMES)]
        path = os.path.join(OUT, f"splat-{mode}.webp")
        frames[0].save(path, save_all=True, append_images=frames[1:], duration=FPS_MS,
                       loop=0, quality=82, method=6, lossless=False)
        print("wrote", path, os.path.getsize(path) // 1024, "KB")


if __name__ == "__main__":
    main()
