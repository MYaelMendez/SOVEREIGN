#!/usr/bin/env python3
"""
ae_boy_studio.py — the æ boy as the Asimov head tablet, rendered by tinyMuJoCo.

Diegetic placement (mujoco-robot-studio): a logo has no body, so it becomes the
robot's FACE — the one surface a robot carries by design. Reuses the EXACT
world->pixel tablet projection from agents/asimov_studio.py, not a new renderer.

Model: the locally published, hash-bound asimov-twin-1.0.0 package (unactuated
asimov_1_25dof.xml, 50 geoms). nu=0 -> open-loop; the still is a PLANT, not an
act. Labeled controllable:false in the receipt.

Run: python ae_boy_studio.py --out ae-boy-studio.png [--yaw 0.0] [--pitch 0.0]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path("C:/æ")
PKG = ROOT / "github-pages/asimov-twin-1.0.0.tar.gz"
STAGE = Path("C:/Users/yaelm/AppData/Local/hermes/cache/scratch/asimov-twin/1.0.0")
MODEL = STAGE / "model/asimov_1_25dof.xml"
LOGO = ROOT / "github-pages/assets/brand/ae-neon-logo.png"
PY = "C:/gpu/Scripts/python.exe"

W, HH = 720, 1280
HDR, VIEW_H = 92, 800
HUD_Y = HDR + VIEW_H
FOVY = 45.0


def ensure_stage() -> dict:
    """Extract the published package once; return its measured hash."""
    sha = hashlib.sha256(PKG.read_bytes()).hexdigest()
    if not MODEL.exists():
        STAGE.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xzf", PKG.as_posix(), "-C", STAGE.parent.as_posix()],
                       check=True)
    return {"package": PKG.name, "sha256": sha, "model": str(MODEL)}


def build_model():
    import mujoco
    src = MODEL.read_text(encoding="utf-8")
    src = re.sub(r'meshdir="[^"]*"', 'meshdir="' + (STAGE / "meshes").as_posix() + '"', src)
    vis = f'<visual><global offwidth="{W}" offheight="{VIEW_H}"/><quality shadowsize="4096"/></visual>'
    src = re.sub(r'<visual>.*?</visual>', vis, src, count=1, flags=re.S) if '<visual>' in src \
        else src.replace('</mujoco>', vis + '</mujoco>')
    m = mujoco.MjModel.from_xml_string(src)
    d = mujoco.MjData(m)
    # DO NOT step: this is the unactuated (nu=0) plant. Its authored initial
    # qpos IS the stand pose (head z=1.12, front +X); stepping falls it over.
    # The skill's settle-to-stand applies to the actuated model with controls.
    mujoco.mj_forward(m, d)
    return mujoco, m, d


def tablet_projection(cam, d, hb, fovy=FOVY):
    """VERBATIM projection geometry from agents/asimov_studio.py:189-209."""
    az_, el_ = math.radians(cam.azimuth), math.radians(cam.elevation)
    dv = np.array([math.cos(el_) * math.cos(az_), math.cos(el_) * math.sin(az_), math.sin(el_)])
    eye = cam.lookat + cam.distance * dv
    fwd = cam.lookat - eye
    fwd = fwd / np.linalg.norm(fwd)
    rt = np.cross(fwd, np.array([0., 0., 1.]))
    rt = rt / np.linalg.norm(rt)
    up = np.cross(rt, fwd)
    R = d.xmat[hb].reshape(3, 3)
    pt = d.xpos[hb] + R @ np.array([0.078, 0.0, 0.040])
    nrm = R @ np.array([1.0, 0.0, 0.0])
    rel = pt - eye
    z = float(np.dot(rel, fwd))
    if z <= 1e-6:
        return None
    f = (VIEW_H / 2.0) / math.tan(math.radians(fovy) / 2.0)
    px = W / 2.0 + f * float(np.dot(rel, rt)) / z
    py = VIEW_H / 2.0 - f * float(np.dot(rel, up)) / z
    facing = abs(float(np.dot(nrm, dv)))
    fw = (f * 0.150) / z * facing
    fh = fw * 0.66
    return (px, py, fw, fh, facing)


def font(sz, bold=False):
    from PIL import ImageFont
    n = "consolab.ttf" if bold else "consola.ttf"
    for p in (Path("C:/Windows/Fonts") / n,
              Path("C:/Windows/Fonts") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")):
        if p.exists():
            return ImageFont.truetype(str(p), sz)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "mp4-factory/ae-boy-studio.png")
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--pitch", type=float, default=0.0)
    ap.add_argument("--azimuth", type=float, default=104.0)
    ap.add_argument("--frames", type=int, default=0,
                    help="if >0, emit a looping GIF with the tablet glow pulsing")
    a = ap.parse_args()

    from PIL import Image, ImageDraw

    prov = ensure_stage()
    mujoco, m, d = build_model()
    hb = m.body("neck_pitch_link").id

    # pose the neck via the named joints (open-loop plant; no commanded motion)
    for name, val in (("neck_yaw_joint", a.yaw), ("neck_pitch_joint", a.pitch)):
        j = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name)
        if j >= 0:
            d.qpos[int(m.jnt_qposadr[j])] = val
    mujoco.mj_forward(m, d)

    r = mujoco.Renderer(m, height=VIEW_H, width=W)
    cam = mujoco.MjvCamera()
    # head is at z~1.12 facing +X; look at the head from its front (azimuth 0)
    head = d.xpos[hb].copy()
    cam.azimuth, cam.elevation, cam.distance = 0.0, 0.0, 1.1
    cam.lookat = head
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    r.update_scene(d, camera=cam)
    base_view = Image.fromarray(r.render()).convert("RGB")

    p = tablet_projection(cam, d, hb)
    placed = False
    logo = Image.open(LOGO).convert("RGBA")
    if p:
        px, py, fw, fh, facing = p
        if fw >= 10 and facing >= 0.25:
            target_h = int(fh)
            target_w = max(1, int(target_h * logo.width / logo.height))
            placed = True

    def make_frame(phase: float) -> Image.Image:
        """phase 0..1: the neon breathes; the physics plant never moves."""
        view = base_view.copy()
        if placed:
            fi = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
            # glow = slow sine, never zero — always legible, only brighter
            # cosine from peak: distinct at every k/60, no duplicate phase
            glow = 0.55 + 0.45 * (0.5 + 0.5 * math.cos(2 * math.pi * phase))
            a = fi.getchannel("A").point(lambda v: int(v * glow))
            fi.putalpha(a)
            view.paste(fi, (int(px - target_w / 2), int(py - target_h / 2)), fi)
        canvas = Image.new("RGB", (W, HH), (11, 10, 6))
        canvas.paste(view, (0, HDR))
        dr = ImageDraw.Draw(canvas, "RGBA")
        dr.rectangle([0, 0, W, HDR], fill=(0, 214, 255, 255))
        dr.text((26, 14), "cli://agentic_environments", font=font(30, True), fill=(5, 5, 5, 255))
        dr.text((26, 55), "THE æ BOY ON THE ASIMOV FACE TABLET · NATIVE MUJOCO",
                font=font(15), fill=(8, 30, 38, 255))
        dr.rectangle([0, HUD_Y, W, HH], fill=(6, 12, 15, 255))
        dr.rectangle([0, HUD_Y, W, HUD_Y + 4], fill=(0, 214, 255, 255))
        lines = [
            "æ.store · agentic environments",
            "face tablet : " + ("æ boy PLACED" if placed else "NOT VISIBLE (angle)"),
            "model : asimov-twin-1.0.0 · 50 geoms · 26 STL",
            "open-loop plant · nu=0 · controllable:false",
            "a plan is never an act",
        ]
        y = HUD_Y + 20
        for ln in lines:
            dr.text((26, y), ln, font=font(18), fill=(180, 240, 255, 255))
            y += 34
        dr.text((26, HH - 60), "sha256 " + prov["sha256"][:24],
                font=font(14), fill=(90, 160, 180, 255))
        return canvas

    canvas = make_frame(0.0)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(a.out)
    receipt = {
        "schema": "ae/ae-boy-studio/1", "artifact": str(a.out),
        "model_sha256": prov["sha256"], "nu": int(m.nu), "ngeom": int(m.ngeom),
        "neck_body_id": int(hb), "tablet_placed": placed,
        "projection": "verbatim asimov_studio.py:189-209",
        "controllable": False, "open_loop": True,
        "note": "a still plant, not a commanded act; logo diegetic as the robot's face",
    }
    if a.frames > 0:
        frames = [make_frame(i / a.frames) for i in range(a.frames)]
        gif = a.out.with_suffix(".gif")
        frames[0].save(gif, save_all=True, append_images=frames[1:],
                       duration=90, loop=0, optimize=False, disposal=2)
        # PIL merges frames whose quantized alpha is byte-identical; record the
        # ACTUAL emitted count by re-opening, never the requested count.
        from PIL import Image as _Im
        emitted = _Im.open(gif).n_frames
        receipt["gif"] = str(gif)
        receipt["frames_requested"] = a.frames
        receipt["frames_emitted"] = emitted
        receipt["gif_bytes"] = gif.stat().st_size
        receipt["note"] = ("physics plant FIXED (nu=0); only the tablet neon "
                           "breathes — no motion claim")
        print(f"wrote {gif} ({gif.stat().st_size} B, {emitted}/{a.frames} frames)")
    rp = a.out.with_suffix(".receipt.json")
    rp.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    print(f"wrote {a.out} ({a.out.stat().st_size} B)")


if __name__ == "__main__":
    main()
