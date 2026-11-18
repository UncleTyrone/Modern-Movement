"""Screen effects drawn on the HUD canvas: the ECHO dash arrows.

On a dash, two ECHO-style chevrons appear around the crosshair on the side you dash toward
(all four directions the same distance from the crosshair, like points around one focal
point), pop in, travel outward and fade in about half a second. Forward and back are wide,
flattened chevrons in slight perspective, so forward reads as "ahead", not "up".

Drawing: with texloader installed, each chevron is one image (textures/mm_dash_side.png and
mm_dash_flat.png, mirrored or flipped for the other directions), the same cost as a compass
icon. The images are copied into texloader's create_textures folder the first time the mod
runs, and texloader loads them the next time the game starts. Without them, every chevron
arm is a thin rotated tile of the engine's white texture, in four layers: a faint dark
backing, a cyan glow, the cyan line and a pale core.
Only numbers are kept between frames (start time and direction weights), never game objects.
The canvas is the one the game passes to the viewport's PostRender each frame.
"""

from __future__ import annotations

import math
import os
import time
import zipfile

import unrealsdk
from mods_base import hook
from unrealsdk.hooks import Type

GLOW = (90, 225, 255)      # ECHO cyan
CORE = (225, 255, 248)     # pale teal-white core
BACK = (5, 20, 30)         # dark backing (keeps it readable on bright skies)

TOTAL = 0.5                # seconds, the whole effect
RADIUS = 92.0              # px from the crosshair at 1125 px tall (scales with the screen)
radius_pct = 250.0         # Dash Arrow Distance (%), locked in
_TEXTURES = ("EngineResources.WhiteSquareTexture", "EngineResources.DefaultTexture")

_arrow: dict | None = None  # {"t0": monotonic, "w": {direction: weight}}
_tex_path: str | None = None
_rot_ok = True             # DrawRotatedTile works (else plain lines are used)
_warned: set = set()


def _warn(key, msg) -> None:
    if key not in _warned:
        _warned.add(key)
        unrealsdk.logging.warning(f"[Modern Movement] {msg}")


def dash_arrows(pc, world_dir) -> None:
    """Start the arrows for a dash going `world_dir` (x, y). The main direction gets full
    strength; a true diagonal also shows the second direction, weaker."""
    global _arrow
    try:
        yaw = int(pc.Rotation.Yaw) * (2.0 * math.pi / 65536.0)
    except Exception:  # noqa: BLE001
        return
    fx_, fy_ = math.cos(yaw), math.sin(yaw)
    dx, dy = world_dir
    fwd = dx * fx_ + dy * fy_
    right = dx * -fy_ + dy * fx_
    w = {}
    for name, v in (("forward", fwd), ("back", -fwd), ("right", right), ("left", -right)):
        if v > 0.0:
            w[name] = v
    top = max(w.values()) if w else 0.0
    weights = {k: min(1.0, v / top) for k, v in w.items() if top > 0 and v / top > 0.55}
    _arrow = {"t0": time.monotonic(), "w": weights}


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _texture():
    global _tex_path
    for path in ((_tex_path,) if _tex_path else _TEXTURES):
        try:
            tex = unrealsdk.find_object("Texture2D", path)
        except Exception:  # noqa: BLE001
            tex = None
        if tex is not None:
            _tex_path = path
            return tex
    return None


# ---- the arrow images (through texloader) -----------------------------------------------
# Slam textures are retained in the source tree for forensic parity with the BL2 baseline but
# are never installed by the TPS co-op package (native Slam owns that presentation).
_IMAGES = (
    "mm_dash_side",
    "mm_dash_flat",
    "mm_pip_outline",
    "mm_pip_fill",
    "mm_jump_chev",
    "mm_slide_bar",
    "mm_slide_cap",
    "mm_surge_arc",
)
SIDE_S = 60.0        # mm_dash_side.png: chevron "s" in image pixels; image centre = chevron centre
FLAT_W = 176.0       # mm_dash_flat.png: chevron half-width in image pixels; image centre = chevron centre
BLEND_TRANSLUCENT = 2
_installed_note = False


def _sdk_mods_dir():
    """(sdk_mods folder, our .sdkmod zip or None, our package folder inside it)."""
    here = os.path.dirname(os.path.abspath(__file__))
    parts = here.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part.lower().endswith(".sdkmod"):
            zpath = "/".join(parts[: i + 1])
            inner = "/".join(parts[i + 1:])
            return os.path.dirname(zpath), zpath, inner
    return os.path.dirname(here), None, here


def install_textures() -> None:
    """Copy the arrow images and their texloader manifests into texloader's create_textures
    folder (only if texloader is there and they are missing or changed). Never raises."""
    global _installed_note
    try:
        root, zpath, inner = _sdk_mods_dir()
        target_root = os.path.join(root, "texloader", "create_textures")
        if not os.path.isdir(target_root):
            return                       # no texloader (or it is a zipped mod): fallback drawing
        changed = []
        zf = zipfile.ZipFile(zpath) if zpath else None
        try:
            for name in _IMAGES:
                for ext in (".png", ".toml"):
                    rel = f"textures/{name}{ext}"
                    if zf is not None:
                        data = zf.read(f"{inner}/{rel}" if inner else rel)
                    else:
                        with open(os.path.join(inner, rel), "rb") as f:
                            data = f.read()
                    dst_dir = os.path.join(target_root, name)
                    dst = os.path.join(dst_dir, name + ext)
                    try:
                        with open(dst, "rb") as f:
                            if f.read() == data:
                                continue
                    except OSError:
                        pass
                    os.makedirs(dst_dir, exist_ok=True)
                    with open(dst, "wb") as f:
                        f.write(data)
                    changed.append(name + ext)
        finally:
            if zf is not None:
                zf.close()
        if changed and not _installed_note:
            _installed_note = True
            unrealsdk.logging.info("[Modern Movement] dash arrow images installed for texloader "
                                   f"({', '.join(changed)}): restart the game to use them")
    except Exception as e:  # noqa: BLE001
        _warn("install", f"dash arrows: could not install the images for texloader ({e!r})")


def _image(name):
    try:
        return unrealsdk.find_object("Texture2D", "Transient." + name)
    except Exception:  # noqa: BLE001
        return None


_lin_cache: dict = {}


def _linear(alpha: float):
    a = round(max(0.0, min(1.0, alpha)), 3)
    c = _lin_cache.get(a)
    if c is None:
        c = unrealsdk.make_struct("LinearColor", R=1.0, G=1.0, B=1.0, A=a)
        if len(_lin_cache) > 2000:
            _lin_cache.clear()
        _lin_cache[a] = c
    return c


def _tile(canvas, tex, cx, cy, w, h, flip_x, flip_y, alpha) -> None:
    """Draw the whole image centred at (cx, cy), w x h on screen, mirrored as asked."""
    sx, sy = float(tex.SizeX), float(tex.SizeY)
    canvas.CurX = cx - w / 2.0
    canvas.CurY = cy - h / 2.0
    canvas.DrawTile(tex, w, h, sx if flip_x else 0.0, sy if flip_y else 0.0,
                    -sx if flip_x else sx, -sy if flip_y else sy, _linear(alpha), False, BLEND_TRANSLUCENT)


def _seg(canvas, tex, x1, y1, x2, y2, width, rgba) -> None:
    """A thick line from (x1, y1) to (x2, y2)."""
    global _rot_ok
    r, g, b, a = rgba
    if a <= 0:
        return
    length = math.hypot(x2 - x1, y2 - y1) + width * 0.5   # a little overlap so joints close
    if length <= 0.5:
        return
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    canvas.SetDrawColor(r, g, b, a)
    if _rot_ok and tex is not None:
        try:
            yaw = int(math.degrees(math.atan2(y2 - y1, x2 - x1)) * 65536.0 / 360.0) & 0xFFFF
            rot = unrealsdk.make_struct("Rotator", Pitch=0, Yaw=yaw, Roll=0)
            canvas.CurX = mx - length / 2.0
            canvas.CurY = my - width / 2.0
            canvas.DrawRotatedTile(tex, rot, length, width, 0, 0, 1, 1, 0.5, 0.5)
            return
        except Exception as e:  # noqa: BLE001
            _rot_ok = False
            _warn("rot", f"dash arrows: rotated tiles unavailable ({e!r}); using lines")
    try:    # fallback: parallel 1-px lines
        n = max(1, int(round(width)))
        nx, ny = -(y2 - y1), (x2 - x1)
        ln = math.hypot(nx, ny) or 1.0
        nx, ny = nx / ln, ny / ln
        colour = unrealsdk.make_struct("Color", R=r, G=g, B=b, A=a)
        for i in range(n):
            o = i - (n - 1) / 2.0
            canvas.Draw2DLine(x1 + nx * o, y1 + ny * o, x2 + nx * o, y2 + ny * o, colour)
    except Exception as e:  # noqa: BLE001
        _warn("line", f"dash arrows: could not draw ({e!r})")


def _chevron(canvas, tex, pts, alpha, width) -> None:
    (ax, ay), (bx, by), (cx, cy) = pts
    for w_mul, colour, amul in ((1.0 + 0.9, BACK, 0.32), (3.2, GLOW, 0.16), (2.0, GLOW, 0.25),
                                (1.0, GLOW, 0.80), (0.45, CORE, 1.0)):
        a = int(255 * alpha * amul)
        w = max(1.0, width * w_mul) if colour is not BACK else width + 2.5
        _seg(canvas, tex, ax, ay, bx, by, w, colour + (a,))
        _seg(canvas, tex, bx, by, cx, cy, w, colour + (a,))


def _draw(canvas) -> None:
    global _arrow
    if _arrow is None:
        return
    t = time.monotonic() - _arrow["t0"]
    if t >= TOTAL + 0.2:
        _arrow = None
        return
    side_img, flat_img = _image("mm_dash_side"), _image("mm_dash_flat")
    images = side_img is not None and flat_img is not None
    tex = None if images else _texture()
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    cx0, cy0 = sw / 2.0, sh / 2.0
    for direction, weight in _arrow["w"].items():
        for i in range(2):                        # two chevrons, the second fainter
            start = i * 0.07
            k = (t - start) / (TOTAL - start - 0.04)
            if k <= 0.0 or k >= 1.0:
                continue
            alpha = _smooth(k / 0.12) * (1.0 - _smooth((k - 0.2) / 0.8)) * (1.0 - 0.4 * i) * weight
            if alpha <= 0.01:
                continue
            r = (RADIUS * radius_pct / 100.0 + i * 30 + _smooth(k) * 22) * u    # outward, never toward the crosshair
            if direction in ("forward", "back"):
                sgn = -1.0 if direction == "forward" else 1.0
                y = cy0 + sgn * r
                persp = (1 - 0.12 * i - 0.1 * _smooth(k)) if direction == "forward" else (1 + 0.08 * i + 0.08 * _smooth(k))
                w, h = 44 * u * persp, 11 * u * persp
                if images:
                    sc = w / FLAT_W
                    _tile(canvas, flat_img, cx0, y, float(flat_img.SizeX) * sc,
                          float(flat_img.SizeY) * sc, False, direction == "back", alpha)
                    continue
                pts = ((cx0 - w, y - sgn * h), (cx0, y + sgn * h), (cx0 + w, y - sgn * h))
                _chevron(canvas, tex, pts, alpha, 6 * u * persp + 1.5)
            else:
                sgn = 1.0 if direction == "right" else -1.0
                x = cx0 + sgn * r
                s = 20 * u * (1 - 0.08 * i)
                if images:
                    sc = s / SIDE_S
                    _tile(canvas, side_img, x, cy0, float(side_img.SizeX) * sc,
                          float(side_img.SizeY) * sc, direction == "left", False, alpha)
                    continue
                pts = ((x - sgn * s * 0.5, cy0 - s), (x + sgn * s * 0.45, cy0), (x - sgn * s * 0.5, cy0 + s))
                _chevron(canvas, tex, pts, alpha, 6 * u)


# BL2 may run its own viewport subclass's PostRender and/or the engine one: lock onto the
# first that fires so the arrows are drawn once a frame.
_HOOK_NAMES = (
    "WillowGame.WillowGameViewportClient:PostRender",
    "Engine.GameViewportClient:PostRender",
)
_source: str | None = None


# ---- dash ready indicator: a small hex below-right of the crosshair that fills from the
# bottom while the dash cools down, then pops with a ring when it is ready and fades out ----
PIP_OFFSET = 46.0          # px right and down from the crosshair at 1125 px tall
PIP_R = 11.0               # hexagon radius on screen at 1125 px tall
PIP_IMG_R = 40.0           # hexagon radius inside the 128 px images
PIP_READY_S = 0.7          # seconds the "ready" pop and ring take to fade
_pip: dict | None = None   # {"p": 0..1} while cooling, {"ready": monotonic} once ready


def pip_progress(p: float) -> None:
    """Cooling down: p = 0 (just dashed) .. 1."""
    global _pip
    _pip = {"p": max(0.0, min(1.0, p))}


def pip_ready() -> None:
    global _pip
    _pip = {"ready": time.monotonic()}


def pip_clear() -> None:
    global _pip
    _pip = None


def _hex_lines(canvas, tex, x, y, r, width, rgba) -> None:
    pts = [(x + r * math.cos(math.radians(-90 + 60 * k)), y + r * math.sin(math.radians(-90 + 60 * k))) for k in range(7)]
    for a, b in zip(pts, pts[1:]):
        _seg(canvas, tex, a[0], a[1], b[0], b[1], width, rgba)


def _draw_pip(canvas) -> None:
    global _pip
    if _pip is None:
        return
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    x, y = sw / 2.0 + PIP_OFFSET * u, sh / 2.0 + PIP_OFFSET * u
    outline, fill = _image("mm_pip_outline"), _image("mm_pip_fill")
    images = outline is not None and fill is not None
    tex = None if images else _texture()
    if "ready" in _pip:
        t = time.monotonic() - _pip["ready"]
        if t >= PIP_READY_S:
            _pip = None
            return
        flash = 1.0 - _smooth(t / PIP_READY_S)
        pop = 1.0 + 0.5 * (1.0 - _smooth(t / 0.25))
        ring = 1.0 + 1.6 * _smooth(t / 0.5)
        ring_a = 0.65 * (1.0 - _smooth(t / 0.5))
        if images:
            size = outline.SizeX * (PIP_R * u / PIP_IMG_R)
            _tile(canvas, fill, x, y, size * pop, size * pop, False, False, flash * 0.9)
            _tile(canvas, outline, x, y, size * pop, size * pop, False, False, flash)
            if ring_a > 0.01:
                _tile(canvas, outline, x, y, size * ring, size * ring, False, False, ring_a)
        else:
            _hex_lines(canvas, tex, x, y, PIP_R * u * pop, 2.5 * u, CORE + (int(255 * flash),))
            if ring_a > 0.01:
                _hex_lines(canvas, tex, x, y, PIP_R * u * ring, 2.0 * u, GLOW + (int(255 * ring_a),))
        return
    p = _pip["p"]
    if images:
        size = outline.SizeX * (PIP_R * u / PIP_IMG_R)
        if p > 0.0:      # the fill: only the bottom part of the image, rising with the cooldown
            sy = float(fill.SizeY)
            top = (PIP_IMG_R * (1.0 - 2.0 * p) + sy / 2.0)          # image row where the fill starts
            top = max(0.0, min(sy, top))
            vis = sy - top
            canvas.CurX = x - size / 2.0
            canvas.CurY = y - size / 2.0 + top * size / sy
            canvas.DrawTile(fill, size, vis * size / sy, 0.0, top, float(fill.SizeX), vis,
                            _linear(0.85), False, BLEND_TRANSLUCENT)
        _tile(canvas, outline, x, y, size, size, False, False, 0.45)
    else:
        _hex_lines(canvas, tex, x, y, PIP_R * u, 2.0 * u, GLOW + (110,))
        rows = int(2 * PIP_R * u * p)
        for i in range(rows):    # rough fill, one line per pixel row from the bottom
            yy = y + PIP_R * u - i
            half = PIP_R * u * 0.85 * (1.0 - abs(yy - y) / (PIP_R * u) * 0.5)
            _seg(canvas, tex, x - half, yy, x + half, yy, 1.0, GLOW + (120,))


# ---- perfect dash: chevrons burst out in all four directions from close to the crosshair,
# brighter and a little bigger than the dash arrows, so it can't be mistaken for a normal dash ----
PERFECT_S = 0.5
_perfect_t: float | None = None


def perfect_dodge() -> None:
    global _perfect_t
    _perfect_t = time.monotonic()


def _one_chevron(canvas, imgs, tex, cx0, cy0, u, direction, r, alpha, scale) -> None:
    """One dash-style chevron `r` px out from the crosshair, pointing outward."""
    side_img, flat_img = imgs
    if direction in ("forward", "back"):
        sgn = -1.0 if direction == "forward" else 1.0
        y = cy0 + sgn * r
        w, h = 44 * u * scale, 11 * u * scale
        if side_img is not None:
            sc = w / FLAT_W
            _tile(canvas, flat_img, cx0, y, float(flat_img.SizeX) * sc, float(flat_img.SizeY) * sc,
                  False, direction == "back", alpha)
            return
        pts = ((cx0 - w, y - sgn * h), (cx0, y + sgn * h), (cx0 + w, y - sgn * h))
        _chevron(canvas, tex, pts, alpha, 6 * u * scale + 1.5)
    else:
        sgn = 1.0 if direction == "right" else -1.0
        x = cx0 + sgn * r
        s = 20 * u * scale
        if side_img is not None:
            sc = s / SIDE_S
            _tile(canvas, side_img, x, cy0, float(side_img.SizeX) * sc, float(side_img.SizeY) * sc,
                  direction == "left", False, alpha)
            return
        pts = ((x - sgn * s * 0.5, cy0 - s), (x + sgn * s * 0.45, cy0), (x - sgn * s * 0.5, cy0 + s))
        _chevron(canvas, tex, pts, alpha, 6 * u * scale)


def _draw_perfect(canvas) -> None:
    global _perfect_t
    if _perfect_t is None:
        return
    t = time.monotonic() - _perfect_t
    if t >= PERFECT_S + 0.1:
        _perfect_t = None
        return
    side_img, flat_img = _image("mm_dash_side"), _image("mm_dash_flat")
    imgs = (side_img, flat_img) if side_img is not None and flat_img is not None else (None, None)
    tex = None if imgs[0] is not None else _texture()
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    cx0, cy0 = sw / 2.0, sh / 2.0
    base = RADIUS * radius_pct / 100.0
    for i in range(2):                                   # two chevrons each way, the second fainter
        k = (t - i * 0.06) / PERFECT_S
        if k <= 0.0 or k >= 1.0:
            continue
        alpha = _smooth(k / 0.1) * (1.0 - _smooth((k - 0.15) / 0.85)) * (1.0 - 0.35 * i)
        if alpha <= 0.01:
            continue
        r = (base * 0.75 + i * 30 + _smooth(k) * 60) * u
        pop = 1.0 + 0.35 * (1.0 - _smooth(k / 0.3))
        for direction in ("forward", "back", "left", "right"):
            # drawn twice: brighter than the normal dash arrows
            _one_chevron(canvas, imgs, tex, cx0, cy0, u, direction, r, alpha, pop)
            _one_chevron(canvas, imgs, tex, cx0, cy0, u, direction, r, alpha * 0.6, pop)


# ---- slam: two landing brackets below the crosshair while a slam is possible (closer together
# and brighter the higher you are), a flash and small drop when the slam starts, and a flat
# shockwave oval on impact, wider for a harder slam. No chevrons: those mean direction. ----
SLAM_Y = 100.0             # px below the crosshair at 1125 px tall
SLAM_LEG = 13.0            # bracket leg length on screen
SLAM_IMG_LEG = 40.0        # bracket leg length inside mm_slam_bracket.png (corner = image centre)
SLAM_SPREAD = (44.0, 24.0)  # bracket corner distance from centre: lowest .. highest
SLAM_RING_S = 0.55
SLAM_RING_IMG_RX = 220.0   # oval half-width inside mm_slam_ring.png
_slam_hud = {"show": False, "charge": 0.0, "shown": 0.0, "level": 0.0, "lock": None, "t": None}
_slam_ring: dict | None = None


def slam_ready(charge: float) -> None:
    """A slam is possible now; charge 0 (just high enough) .. 1 (as hard as it gets)."""
    _slam_hud["show"] = True
    _slam_hud["charge"] = max(0.0, min(1.0, charge))
    _slam_hud["lock"] = None


def slam_go() -> None:
    _slam_hud["show"] = True
    _slam_hud["lock"] = time.monotonic()


def slam_hide() -> None:
    _slam_hud["show"] = False


def slam_impact(strength: float) -> None:
    global _slam_ring
    _slam_hud["show"] = False
    _slam_hud["level"] = 0.0
    _slam_hud["lock"] = None
    _slam_ring = {"t0": time.monotonic(), "s": max(0.0, min(1.0, strength))}


def _slam_active() -> bool:
    return _slam_hud["show"] or _slam_hud["level"] > 0.0 or _slam_ring is not None


def _draw_slam(canvas) -> None:
    global _slam_ring
    h = _slam_hud
    now = time.monotonic()
    dt = 0.0 if h["t"] is None else min(0.1, now - h["t"])
    h["t"] = now
    h["level"] = max(0.0, min(1.0, h["level"] + (dt / 0.12 if h["show"] else -dt / 0.15)))
    h["shown"] += (h["charge"] - h["shown"]) * min(1.0, dt * 12.0)
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    cx, cy = sw / 2.0, sh / 2.0 + SLAM_Y * u
    br_img = _image("mm_slam_bracket")
    tex = None
    if h["level"] > 0.0:
        c = _smooth(h["shown"])
        spread = SLAM_SPREAD[0] + (SLAM_SPREAD[1] - SLAM_SPREAD[0]) * c
        alpha = (0.45 + 0.55 * c) * _smooth(h["level"])
        drop = 0.0
        if h["lock"] is not None:
            p = now - h["lock"]
            alpha = min(1.0, alpha + 0.5 * (1.0 - _smooth(p / 0.25)))
            drop = 3.0 * _smooth(p / 0.12)
        y = cy + drop * u
        if br_img is not None:
            size = float(br_img.SizeX) * SLAM_LEG * u / SLAM_IMG_LEG
            # the image's corner is its centre; the left bracket's foot points right (inward)
            _tile(canvas, br_img, cx - spread * u, y, size, size, False, False, alpha)
            _tile(canvas, br_img, cx + spread * u, y, size, size, True, False, alpha)
            if h["lock"] is not None and alpha > 0.9:      # extra brightness for the flash
                _tile(canvas, br_img, cx - spread * u, y, size, size, False, False, alpha - 0.9)
                _tile(canvas, br_img, cx + spread * u, y, size, size, True, False, alpha - 0.9)
        else:
            tex = _texture()
            leg, foot = SLAM_LEG * u, 11.0 * u
            for sgn in (-1.0, 1.0):
                x = cx + sgn * spread * u
                _chevron(canvas, tex, ((x, y - leg), (x, y), (x - sgn * foot, y)), alpha, 3.4 * u + 1.0)
    if _slam_ring is not None:
        t = now - _slam_ring["t0"]
        if t >= SLAM_RING_S + 0.15:
            _slam_ring = None
            return
        ring_img = _image("mm_slam_ring")
        if ring_img is None and tex is None:
            tex = _texture()
        for delay, amul in ((0.0, 1.0), (0.12, 0.55)):
            k = (t - delay) / SLAM_RING_S
            if k <= 0.0 or k >= 1.0:
                continue
            rx = (18.0 + (60.0 + 120.0 * _slam_ring["s"]) * _smooth(k)) * u
            a = amul * (1.0 - _smooth((k - 0.1) / 0.9))
            if a <= 0.01:
                continue
            if ring_img is not None:
                sc = rx / SLAM_RING_IMG_RX
                _tile(canvas, ring_img, cx, cy, float(ring_img.SizeX) * sc, float(ring_img.SizeY) * sc,
                      False, False, a)
            else:
                ry = rx * 0.26
                pts = [(cx + rx * math.cos(math.radians(15 * i)), cy + ry * math.sin(math.radians(15 * i)))
                       for i in range(25)]
                for p0, p1 in zip(pts, pts[1:]):
                    _seg(canvas, tex, p0[0], p0[1], p1[0], p1[1], 2.5 * u + 0.5, GLOW + (int(255 * a),))


# ---- slide: a momentum bar below the crosshair (where the slam brackets go, which only show in
# the air) that shrinks toward the centre as the slide loses speed. A slide jump makes it flash,
# stretch and lift away; a slide that ends any other way fades it out. ----
SLIDE_Y = 120.0            # px below the crosshair at 1125 px tall
SLIDE_HALF = (8.0, 60.0)   # bar half-width: no momentum .. full
SLIDE_THICK = 12.0         # drawn height of mm_slide_bar.png (its line is about a fifth of that)
SLIDE_CAP = 15.0           # drawn height of mm_slide_cap.png
SLIDE_LAUNCH_S = 0.35
_slide_hud = {"on": False, "v": 0.0, "shown": 0.0, "level": 0.0, "launch": None, "t": None}


def slide_momentum(v: float) -> None:
    """Sliding, with v = 0 (about to stop) .. 1 (the speed it started at)."""
    h = _slide_hud
    if not h["on"]:
        h["shown"] = max(0.0, min(1.0, v))
    h["on"] = True
    h["launch"] = None
    h["v"] = max(0.0, min(1.0, v))


def slide_end() -> None:
    _slide_hud["on"] = False


def slide_launch() -> None:
    h = _slide_hud
    h["on"] = False
    h["level"] = max(h["level"], 1.0)
    h["launch"] = time.monotonic()


def _slide_active() -> bool:
    return _slide_hud["on"] or _slide_hud["level"] > 0.0


def _draw_slide(canvas) -> None:
    h = _slide_hud
    now = time.monotonic()
    dt = 0.0 if h["t"] is None else min(0.1, now - h["t"])
    h["t"] = now
    stretch, lift, boost = 1.0, 0.0, 0.0
    if h["launch"] is not None:
        k = (now - h["launch"]) / SLIDE_LAUNCH_S
        if k >= 1.0:
            h["launch"] = None
            h["level"] = 0.0
            return
        stretch, lift, boost = 1.0 + 0.5 * _smooth(k), -10.0 * _smooth(k), 0.6 * (1.0 - _smooth(k / 0.5))
        level = 1.0 - _smooth(k)
    else:
        h["level"] = max(0.0, min(1.0, h["level"] + (dt / 0.1 if h["on"] else -dt / 0.2)))
        level = _smooth(h["level"])
        h["shown"] += (h["v"] - h["shown"]) * min(1.0, dt * 15.0)
    if level <= 0.0:
        return
    v = h["shown"]
    alpha = min(1.0, (0.45 + 0.55 * v) * level)
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    cx, y = sw / 2.0, sh / 2.0 + (SLIDE_Y + lift) * u
    half = (SLIDE_HALF[0] + (SLIDE_HALF[1] - SLIDE_HALF[0]) * v) * u * stretch
    bar_img, cap_img = _image("mm_slide_bar"), _image("mm_slide_cap")
    passes = [(alpha, )] + ([(min(1.0, boost),)] if boost > 0.01 else [])
    if bar_img is not None and cap_img is not None:
        cap_w = float(cap_img.SizeX) * SLIDE_CAP * u / float(cap_img.SizeY)
        for (a,) in passes:
            _tile(canvas, bar_img, cx, y, 2.0 * half, SLIDE_THICK * u, False, False, a)
            _tile(canvas, cap_img, cx - half, y, cap_w, SLIDE_CAP * u, False, False, a)
            _tile(canvas, cap_img, cx + half, y, cap_w, SLIDE_CAP * u, False, False, a)
    else:
        tex = _texture()
        a = min(1.0, alpha + boost)
        cap = SLIDE_CAP * u * 0.4
        for p0, p1 in (((cx - half, y), (cx + half, y)), ((cx - half, y - cap), (cx - half, y + cap)),
                       ((cx + half, y - cap), (cx + half, y + cap))):
            mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
            _chevron(canvas, tex, (p0, mid, p1), a, 3.0 * u + 1.0)


# ---- Sprint Surge: two arcs either side of the crosshair while surging. Each grows out from its
# middle when it starts, pushes outward and brightens as the boost ramps up, pulses at full boost
# and then sweeps away. Blocking an action skill flickers them (bringing them back briefly at full
# boost). Ending a surge before full boost opens them outward and fades them. ----
SURGE_R = (120.0, 195.0)   # arc radius on screen at 1125 px tall: just started .. full boost
SURGE_GROW_S = 0.25        # seconds for an arc to grow out from its middle
SURGE_AWAY_AFTER = 0.3     # seconds after reaching full boost that the arcs sweep away
SURGE_BLOCK_SHOW = 0.85    # seconds the arcs come back for when an action skill is blocked at full boost
SURGE_IMG_R = 200.0        # arc radius inside mm_surge_arc.png (96 x 256)
SURGE_IMG_OFF = 178.0      # image centre's distance from the arc's circle centre, in image pixels
_surge = {"on": False, "ramp": 0.0, "t_on": 0.0, "t_off": None, "t_full": None, "t_block": None}


def surge_state(active: bool, ramp: float) -> None:
    """Called every tick: surging or not, and how far the boost has ramped (0 .. 1)."""
    s = _surge
    now = time.monotonic()
    if active:
        if not s["on"]:
            s.update(on=True, t_on=now, t_off=None, t_full=None, t_block=None)
        s["ramp"] = max(0.0, min(1.0, ramp))
        if s["ramp"] >= 1.0 and s["t_full"] is None:
            s["t_full"] = now
    elif s["on"]:
        s["on"] = False
        s["t_off"] = now


def surge_blocked() -> None:
    if _surge["on"]:
        _surge["t_block"] = time.monotonic()


def _surge_active() -> bool:
    return _surge["on"] or _surge["t_off"] is not None


def _draw_surge(canvas) -> None:
    s = _surge
    if not _surge_active():
        return
    now = time.monotonic()
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    cx, cy = sw / 2.0, sh / 2.0
    lin = s["ramp"]
    r = (SURGE_R[0] + (SURGE_R[1] - SURGE_R[0]) * _smooth(lin)) * u
    alpha = 0.40 + 0.25 * lin + 0.08 * math.sin(2.0 * math.pi * (now - s["t_on"]) / 1.6)
    length = _smooth((now - s["t_on"]) / SURGE_GROW_S)        # 0 .. 1 of the arc, from its middle
    if s["t_full"] is not None and now - s["t_full"] < 0.45:
        alpha += 0.5 * (1.0 - _smooth((now - s["t_full"]) / 0.45))
    away = s["t_full"] is not None and now >= s["t_full"] + SURGE_AWAY_AFTER
    block = None if s["t_block"] is None else now - s["t_block"]
    if away:
        # at full boost the arcs pulse, then sweep outward and fade; they only come back (growing out
        # from their middles, flickering, sweeping away again) if an action skill is blocked
        gone_at = s["t_full"] + SURGE_AWAY_AFTER
        if block is not None and s["t_block"] >= gone_at and block < SURGE_BLOCK_SHOW:
            length = _smooth(block / SURGE_GROW_S)
            fl = 1.0 - _smooth(block / 0.4)
            alpha += 0.7 * fl * (0.6 + 0.4 * math.cos(block * 40.0))
            r -= 6.0 * u * fl
            k = (block - 0.5) / 0.35
            if k > 0.0:
                r += 90.0 * u * _smooth(k)
                alpha *= 1.0 - _smooth(k)
        else:
            if block is not None and block >= SURGE_BLOCK_SHOW:
                s["t_block"] = None
            k = (now - gone_at) / 0.35
            if block is not None and s["t_block"] is not None and s["t_block"] < gone_at and block < 0.4:
                fl = 1.0 - _smooth(block / 0.4)         # blocked just as they were leaving
                alpha += 0.7 * fl * (0.6 + 0.4 * math.cos(block * 40.0))
            if k >= 1.0:
                if s["t_off"] is not None:
                    s["t_off"] = None                     # the surge ended after they left: nothing to show
                return
            r += 90.0 * u * _smooth(k)
            alpha *= 1.0 - _smooth(k)
        if s["t_off"] is not None and now - s["t_off"] > SURGE_BLOCK_SHOW:
            s["t_off"] = None
            return
    else:
        if block is not None:
            if block < 0.4:
                fl = 1.0 - _smooth(block / 0.4)
                alpha += 0.7 * fl * (0.6 + 0.4 * math.cos(block * 40.0))
                r -= 6.0 * u * fl
            else:
                s["t_block"] = None
        if s["t_off"] is not None:
            k = (now - s["t_off"]) / 0.35
            if k >= 1.0:
                s["t_off"] = None
                return
            r += 90.0 * u * _smooth(k)                         # opening outward as it fades
            alpha *= 1.0 - _smooth(k)
    if alpha <= 0.01 or length <= 0.01:
        return
    img = _image("mm_surge_arc")
    if img is not None:
        sc = r / SURGE_IMG_R
        iw, ih = float(img.SizeX), float(img.SizeY)
        w = iw * sc
        vis = ih * length                                     # rows of the image shown, around its middle
        v0 = (ih - vis) / 2.0
        off = SURGE_IMG_OFF * sc
        a = alpha
        while a > 0.01:                               # over 1 = drawn again on top (brighter)
            for sgn in (1.0, -1.0):
                canvas.CurX = cx + sgn * off - w / 2.0
                canvas.CurY = cy - vis * sc / 2.0
                canvas.DrawTile(img, w, vis * sc, iw if sgn < 0 else 0.0, v0, -iw if sgn < 0 else iw, vis,
                                _linear(min(1.0, a)), False, BLEND_TRANSLUCENT)
            a -= 1.0
    else:
        tex = _texture()
        a = min(1.0, alpha)
        span = 30.0 * length
        for sgn in (-1.0, 1.0):
            pts = [(cx + sgn * r * math.cos(math.radians(span * i / 3.0)), cy + r * math.sin(math.radians(span * i / 3.0)))
                   for i in range(-3, 4)]
            for p0, p1 in zip(pts, pts[1:]):
                _seg(canvas, tex, p0[0], p0[1], p1[0], p1[1], 2.5 * u + 0.5, GLOW + (int(255 * a),))


# ---- jump counter: up-chevrons below-left of the crosshair (mirroring the ready hex) ----
JUMP_W = 11.0
JUMP_STEP = 11.0
JUMP_IMG_W = 60.0
JUMP_FADE_IN = 0.15
JUMP_FADE_OUT = 0.2
JUMP_SPEND_S = 0.35
_jump = {"total": 0, "left": 0, "air": False, "level": 0.0, "t": None, "spent": []}


def jump_state(left: int, total: int, airborne: bool) -> None:
    """Called every tick by double jump: jumps left, Extra Jumps setting, in the air."""
    j = _jump
    now = time.monotonic()
    if airborne and left < j["left"] and j["air"]:
        for i in range(left, j["left"]):
            j["spent"].append((i, now))
    if airborne or j["level"] <= 0.0:
        j["left"] = max(0, left)
    j["total"], j["air"] = max(0, total), airborne


def _jump_layout(total: int):
    k = 1.0 if total <= 3 else 3.0 / total * 1.15
    sc = 1.0 if total <= 3 else 0.9
    return [(i * JUMP_STEP * k, sc) for i in range(total)]


def _draw_jumps(canvas) -> None:
    j = _jump
    now = time.monotonic()
    t_prev = j["t"]
    j["t"] = now
    dt = 0.0 if t_prev is None else min(0.1, now - t_prev)
    target = 1.0 if (j["air"] and j["total"] > 0) else 0.0
    rate = (1.0 / JUMP_FADE_IN) if target > j["level"] else (1.0 / JUMP_FADE_OUT)
    j["level"] = max(0.0, min(1.0, j["level"] + (rate * dt if target > j["level"] else -rate * dt)))
    j["spent"] = [(i, t0) for i, t0 in j["spent"] if now - t0 < JUMP_SPEND_S]
    if j["level"] <= 0.0 and not j["spent"]:
        return
    sw, sh = float(canvas.ClipX), float(canvas.ClipY)
    u = sh / 1125.0
    x = sw / 2.0 - PIP_OFFSET * u
    y0 = sh / 2.0 + (PIP_OFFSET + 9.0) * u
    img = _image("mm_jump_chev")
    tex = None if img is not None else _texture()
    layout = _jump_layout(j["total"])

    def chev(i, alpha, rise=0.0, grow=1.0):
        if i >= len(layout) or alpha <= 0.01:
            return
        dy, sc = layout[i]
        w = JUMP_W * u * sc * grow
        yy = y0 - (dy + rise) * u
        if img is not None:
            s = w / JUMP_IMG_W
            _tile(canvas, img, x, yy, float(img.SizeX) * s, float(img.SizeY) * s, False, False, alpha)
        else:
            h = w * 0.3
            _chevron(canvas, tex, ((x - w, yy + h), (x, yy - h), (x + w, yy + h)), alpha, 5 * u * sc + 0.5)

    smooth_level = _smooth(j["level"])
    for i in range(min(j["left"], len(layout))):
        chev(i, smooth_level)
    for i, t0 in j["spent"]:
        k = _smooth((now - t0) / JUMP_SPEND_S)
        chev(i, (1.0 - k) * max(smooth_level, 0.6), rise=8.0 * k, grow=1.0 + 0.3 * k)


def _on_post_render(name: str, args) -> None:
    global _source
    if (
        _arrow is None
        and _pip is None
        and _perfect_t is None
        and not _slam_active()
        and not _slide_active()
        and not _surge_active()
        and _jump["level"] <= 0.0
        and not _jump["air"]
        and not _jump["spent"]
    ):
        _jump["t"] = None
        return
    if _source is None:
        _source = name
    elif _source != name:
        return
    try:
        canvas = args.Canvas
        if canvas is not None:
            _draw(canvas)
            _draw_pip(canvas)
            _draw_perfect(canvas)
            _draw_slam(canvas)
            _draw_slide(canvas)
            _draw_surge(canvas)
            _draw_jumps(canvas)
    except Exception as e:  # noqa: BLE001
        _warn("draw", f"dash arrows: draw failed ({e!r})")


def _make_hook(name: str):
    def _cb(obj, args, ret, func) -> None:
        _on_post_render(name, args)
    _cb.__name__ = "mm_hudfx_" + name.split(".")[0].lower()
    _cb.__qualname__ = _cb.__name__
    return hook(name, Type.POST)(_cb)


HOOKS = [_make_hook(n) for n in _HOOK_NAMES]


def reset() -> None:
    global _arrow, _source, _rot_ok, _pip, _perfect_t, _slam_ring
    _arrow = None
    _perfect_t = None
    _pip = None
    _slam_ring = None
    _slam_hud.update(show=False, charge=0.0, shown=0.0, level=0.0, lock=None, t=None)
    _slide_hud.update(on=False, v=0.0, shown=0.0, level=0.0, launch=None, t=None)
    _surge.update(on=False, ramp=0.0, t_on=0.0, t_off=None, t_full=None, t_block=None)
    _jump.update(total=0, left=0, air=False, level=0.0, t=None, spent=[])
    _source = None
    _rot_ok = True
