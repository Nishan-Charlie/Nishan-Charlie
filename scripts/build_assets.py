"""Builds the animated SVG assets used by the profile README.

Palette is deliberately small: one text colour, one muted grey, one faint
grey for lines, and a single amber accent. Every asset is written in a dark
and a light variant; the README picks one with <picture> to follow the
viewer's GitHub theme.

The 3D objects are real 3D geometry: each frame is projected in Python and
the frames are played back with SMIL <animate values="...">, so no
JavaScript is needed (GitHub strips scripts from README images).

Usage:  python scripts/build_assets.py      (writes into ./assets)
"""
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
os.makedirs(OUT, exist_ok=True)

THEMES = {
    "dark": dict(text="#e6edf3", muted="#7d8590", faint="#30363d", accent="#e3b341",
                 card="#0d1117", on_accent="#0d1117"),
    "light": dict(text="#1f2328", muted="#656d76", faint="#d0d7de", accent="#9a6700",
                  card="#ffffff", on_accent="#ffffff"),
}
SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, 'Courier New', monospace"


def write(name, svg):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(svg)


# ------------------------------------------------------------------ 3D helpers
def icosphere(subdiv=1):
    """Unit icosphere: returns (vertices, edges)."""
    p = (1 + 5 ** 0.5) / 2
    verts = [(-1, p, 0), (1, p, 0), (-1, -p, 0), (1, -p, 0), (0, -1, p), (0, 1, p),
             (0, -1, -p), (0, 1, -p), (p, 0, -1), (p, 0, 1), (-p, 0, -1), (-p, 0, 1)]
    verts = [tuple(c / math.sqrt(sum(x * x for x in v)) for c in v) for v in verts]
    faces = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
             (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
             (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(subdiv):
        cache, nf = {}, []

        def mid(a, b):
            key = tuple(sorted((a, b)))
            if key not in cache:
                m = [(verts[a][k] + verts[b][k]) / 2 for k in range(3)]
                n = math.sqrt(sum(x * x for x in m))
                verts.append(tuple(x / n for x in m))
                cache[key] = len(verts) - 1
            return cache[key]

        for a, b, c in faces:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        faces = nf
    edges = set()
    for a, b, c in faces:
        for e in ((a, b), (b, c), (c, a)):
            edges.add(tuple(sorted(e)))
    return verts, sorted(edges)


def lattice_cube(n=3):
    """Points of an n x n x n lattice plus the 12 cube edges."""
    s = [-1 + 2 * i / (n - 1) for i in range(n)]
    pts = [(x, y, z) for x in s for y in s for z in s]
    corners = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    edges = [(i, j) for i in range(8) for j in range(i + 1, 8)
             if sum(a != b for a, b in zip(corners[i], corners[j])) == 1]
    return pts, corners, edges


def project(v, ay, ax, scale, cx, cy, dist=4.0):
    x, y, z = v
    # rotate around Y then X
    x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
    y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
    f = dist / (dist - z)
    return cx + x * scale * f, cy + y * scale * f, z


def frames_of(points, n_frames, ax_fn, scale, cx, cy):
    out = []
    for k in range(n_frames + 1):
        t = 2 * math.pi * k / n_frames
        out.append([project(p, t, ax_fn(t), scale, cx, cy) for p in points])
    return out


def anim(attr, vals, dur):
    return (f'<animate attributeName="{attr}" dur="{dur}s" repeatCount="indefinite" '
            f'values="{";".join(vals)}"/>')


def mesh_svg(points, edges, scale, cx, cy, dur, t, n_frames=72, ax_fn=None,
             point_r=(0.8, 2.6), edge_points=None):
    ax_fn = ax_fn or (lambda t_: 0.42 + 0.18 * math.sin(t_))
    fr = frames_of(points, n_frames, ax_fn, scale, cx, cy)
    ep = edge_points if edge_points is not None else points
    efr = fr if edge_points is None else frames_of(ep, n_frames, ax_fn, scale, cx, cy)
    d_vals = [" ".join(f"M{f[a][0]:.1f} {f[a][1]:.1f}L{f[b][0]:.1f} {f[b][1]:.1f}" for a, b in edges)
              for f in efr]
    parts = [f'<path d="{d_vals[0]}" fill="none" stroke="{t["muted"]}" stroke-width=".7" '
             f'stroke-opacity=".55">{anim("d", d_vals, dur)}</path>']
    lo, hi = point_r
    for i in range(len(points)):
        xs = [f"{f[i][0]:.1f}" for f in fr]
        ys = [f"{f[i][1]:.1f}" for f in fr]
        rs = [f"{lo + (hi - lo) * (f[i][2] + 1) / 2:.2f}" for f in fr]
        os_ = [f"{0.25 + 0.75 * (f[i][2] + 1) / 2:.2f}" for f in fr]
        parts.append(f'<circle cx="{xs[0]}" cy="{ys[0]}" r="{rs[0]}" fill="{t["text"]}">'
                     f'{anim("cx", xs, dur)}{anim("cy", ys, dur)}{anim("r", rs, dur)}'
                     f'{anim("fill-opacity", os_, dur)}</circle>')
    return "".join(parts)


# ------------------------------------------------------------------ banner
def banner(t):
    W, H = 860, 210
    verts, edges = icosphere(1)
    mesh = mesh_svg(verts, edges, 62, 100, 100, 16, t)

    nx, ny, nw = 215, 98, 560
    bx, by, bw, bh = nx - 14, ny - 46, nw + 28, 64
    per = 2 * (bw + bh)
    c = 16
    corners = " ".join(
        f"M{x + dx * c},{y} L{x},{y} L{x},{y + dy * c}"
        for x, y, dx, dy in [(bx, by, 1, 1), (bx + bw, by, -1, 1),
                             (bx, by + bh, 1, -1), (bx + bw, by + bh, -1, -1)])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Nishankar Sathiyamohan, computer vision researcher">
<defs>
  <linearGradient id="scan" x1="0" x2="1">
    <stop offset="0" stop-color="{t['accent']}" stop-opacity="0"/>
    <stop offset="1" stop-color="{t['accent']}" stop-opacity=".45"/>
  </linearGradient>
  <clipPath id="boxclip"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}"/></clipPath>
  <style>
    .name {{ font: 700 44px {SANS}; fill:{t['text']}; fill-opacity:0; stroke:{t['text']}; stroke-width:1;
             stroke-dasharray:420; stroke-dashoffset:420; animation: draw 2.2s ease-out .2s forwards, fillin .8s ease 1.8s forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset:0 }} }}
    @keyframes fillin {{ to {{ fill-opacity:1; stroke-width:0 }} }}
    .box {{ fill:none; stroke:{t['muted']}; stroke-width:1; stroke-dasharray:{per}; stroke-dashoffset:{per};
            animation: draw 1.1s ease-in-out 2.4s forwards; }}
    .corner {{ fill:none; stroke:{t['accent']}; stroke-width:3; stroke-linecap:round; opacity:0; animation: show .3s ease 3.3s forwards; }}
    .late {{ opacity:0; animation: show .5s ease 3.5s forwards; }}
    .sub {{ opacity:0; animation: show .9s ease 3.9s forwards; }}
    .fade {{ opacity:0; animation: show 1.2s ease .2s forwards; }}
    @keyframes show {{ to {{ opacity:1 }} }}
    .scanbar {{ animation: sweep 3.2s linear 3.6s infinite; }}
    @keyframes sweep {{ from {{ transform: translateX(0) }} to {{ transform: translateX({bw + 60}px) }} }}
  </style>
</defs>

<g class="fade">{mesh}</g>
<text x="100" y="196" text-anchor="middle" class="fade" style="font: 600 11px {MONO}; fill:{t['muted']}; letter-spacing:.06em">mesh.rotate(y)</text>

<text x="{nx}" y="{ny}" class="name" textLength="{nw}" lengthAdjust="spacingAndGlyphs">Nishankar Sathiyamohan</text>
<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="3" class="box"/>
<path d="{corners}" class="corner"/>
<g class="late" clip-path="url(#boxclip)"><rect class="scanbar" x="{bx - 60}" y="{by}" width="60" height="{bh}" fill="url(#scan)"/></g>
<g class="late">
  <rect x="{bx}" y="{by - 24}" width="142" height="22" rx="3" fill="{t['accent']}"/>
  <text x="{bx + 9}" y="{by - 8.5}" style="font: 700 12.5px {MONO}; fill:{t['on_accent']}">researcher 0.98</text>
</g>

<text x="{bx}" y="{by + bh + 40}" class="sub" style="font: 600 16px {MONO}; fill:{t['muted']}">Computer Vision  /  Explainable AI  /  Medical Image Analysis</text>
</svg>
'''


# ------------------------------------------------------------------ hero line
def hero(t):
    W, H, fs = 800, 64, 24
    cw = fs * 0.6
    parts = [(">>> ", t["muted"]), ("vision", t["text"]), (".see", t["accent"]), ("(", t["muted"]),
             ("world", t["text"]), (")", t["muted"]), (".explain", t["accent"]), ("(", t["muted"]),
             ("why", t["text"]), (")", t["muted"])]
    chars = [(ch, col) for s, col in parts for ch in s]
    x0 = (W - len(chars) * cw) / 2
    step = 0.075
    spans = "\n".join(
        f'<text x="{x0 + k * cw:.1f}" y="40" fill="{col}" class="ch" style="animation-delay:{0.6 + k * step:.3f}s">{ch}</text>'
        for k, (ch, col) in enumerate(chars) if ch != " ")
    dx = len(chars) * cw + 3
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="vision.see(world).explain(why)">
<style>
  .ch {{ opacity:0; animation: on .01s linear forwards; }}
  @keyframes on {{ to {{ opacity:1 }} }}
  .cur {{ animation: move {len(chars) * step:.2f}s steps({len(chars)}) .6s forwards, blink 1s step-end infinite; }}
  @keyframes move {{ to {{ transform: translateX({dx:.1f}px) }} }}
  @keyframes blink {{ 50% {{ opacity:0 }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{t['faint']}"/>
<g style="font: 700 {fs}px {MONO}">
{spans}
</g>
<rect x="{x0:.1f}" y="22" width="{cw * 0.6:.1f}" height="24" fill="{t['accent']}" class="cur"/>
</svg>
'''


# ------------------------------------------------------------------ toolkit card
def toolkit(t):
    groups = [
        ("Research", ["Python", "PyTorch", "TensorFlow", "Hugging Face", "OpenCV", "NumPy"]),
        ("Engineering", ["Java", "JavaScript", "C", "PHP", "Android", "Firebase"]),
        ("Tools", ["Git", "Linux", "MySQL", "GCP", "Blender", "Arduino"]),
    ]
    W = 495
    body = [f'<text x="25" y="34" style="font: 600 18px {SANS}; fill:{t["text"]}">Toolkit</text>']
    y, d = 54, 0
    for label, items in groups:
        body.append(f'<text x="25" y="{y + 16}" style="font: 600 11px {MONO}; fill:{t["muted"]}">{label}</text>')
        x = 115
        for name in items:
            w = 16 + len(name) * 7.4
            if x + w > W - 18:
                x, y = 115, y + 32
            body.append(
                f'<g class="st" style="animation-delay:{d}ms"><rect x="{x}" y="{y}" width="{w:.0f}" height="24" rx="5" '
                f'fill="none" stroke="{t["faint"]}"/><text x="{x + w / 2:.1f}" y="{y + 16.5}" text-anchor="middle" '
                f'style="font: 600 12.5px {SANS}" fill="{t["text"]}">{name}</text></g>')
            x += w + 7
            d += 60
        y += 40
    H = y + 6
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Toolkit">
<style>.st {{ opacity:0; animation: fade .4s ease forwards; }} @keyframes fade {{ to {{ opacity:1 }} }}</style>
<rect width="{W}" height="{H}" rx="4.5" fill="{t['card']}"/>
<rect x="25" y="42" width="28" height="2" fill="{t['accent']}"/>
{chr(10).join(body)}
</svg>
'''


# ------------------------------------------------------------------ footer: 3D voxel lattice
def footer(t):
    W = H = 130
    pts, corners, edges = lattice_cube(3)
    ax_fn = lambda t_: 0.55 + 0.25 * math.sin(2 * t_)
    mesh = mesh_svg(pts, edges, 27, W / 2, H / 2, 12, t, n_frames=72, ax_fn=ax_fn,
                    point_r=(1.2, 3.4), edge_points=corners)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Rotating 3D point lattice">
{mesh}
<circle cx="{W / 2}" cy="{H / 2}" r="3.6" fill="{t['accent']}"/>
</svg>
'''


for mode, th in THEMES.items():
    write(f"banner-{mode}.svg", banner(th))
    write(f"hero-{mode}.svg", hero(th))
    write(f"toolkit-{mode}.svg", toolkit(th))
print("assets written to", OUT)
