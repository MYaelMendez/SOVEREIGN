#!/usr/bin/env python3
"""
neon_asimov.py — the robot IS the neon. Emissive geometry, no lighting dependency.

The real Asimov twin's own geoms are assigned an emissive material (mat_emission)
and the scene gets a strong ambient light. MuJoCo's real depth pass stays on.
Every render is locked to exact 9:16: 576x1024, ratio 0.5625.

  python neon_asimov.py --still     measured still + IHDR check
  python neon_asimov.py --film      14 verb stages -> MP4 + gate + receipt
"""
from __future__ import annotations

import argparse, hashlib, json, subprocess, sys
from pathlib import Path

import numpy as np

ROOT = Path('C:/æ/mp4-factory')
sys.path.insert(0, str(ROOT)); sys.path.insert(0, 'C:/æ/agents')
import neon_holomesh as nh
import neon_rule_env as nre

W, H, VIEW_H = 576, 1024, 768
assert W / H == 0.5625
FPS, PER_VERB = 24, 8
FFMPEG = Path('C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe')
RES = json.loads((ROOT / 'NEON-STUDIO-RESOURCES.json').read_text(encoding='utf-8'))
TRACE = json.loads(Path(RES['trace']['path']).read_text(encoding='utf-8'))
VERBS = sorted(RES['verbs']['table'])


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def font(sz, bold=False):
    from PIL import ImageFont
    p = Path('C:/Windows/Fonts') / ('consolab.ttf' if bold else 'consola.ttf')
    return ImageFont.truetype(str(p), sz) if p.exists() else ImageFont.load_default()


def stage_for(cls):
    return {'read': ('observe', 'PUBLIC'),
            'media': ('produce', 'PUBLISHED'),
            'motion': ('act', 'CUSTODY')}[cls]


def build():
    import mujoco
    xml = nh.build_xml()
    # Emissive material for the robot's OWN geoms; ambient light as a floor.
    mat = ('<material name="neon_body" rgba="0.10 0.35 0.40 1" emission="1"/>')
    xml = xml.replace('</asset>', mat + '\n</asset>')
    ambient = ('<light name="neon_ambient" type="directional" pos="0 0 2" dir="0 0 -1" '
               'ambient="0.85 0.85 0.85" diffuse="0.35 0.35 0.35" specular="0.2 0.2 0.2"/>')
    xml = xml.replace('</worldbody>', ambient + '\n</worldbody>')
    m = mujoco.MjModel.from_xml_string(xml)
    mid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_MATERIAL, 'neon_body')
    if mid < 0:
        raise RuntimeError('neon_body material not compiled')
    m.mat_emission[mid] = 1.0
    for g in range(m.ngeom):
        name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or ''
        if not name.startswith('neon_'):
            m.geom_matid[g] = mid
    d = mujoco.MjData(m)
    r = mujoco.Renderer(m, height=VIEW_H, width=W)
    r.enable_depth_rendering()
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.azimuth, cam.elevation, cam.distance = 90.0, -5.0, 2.6
    cam.lookat = np.array([0.54, 0.0, 0.50])
    return mujoco, m, d, r, cam


def frame(idx, ctx):
    mujoco, m, d, r, cam = ctx
    from PIL import Image, ImageDraw, ImageFilter
    verb = VERBS[idx // PER_VERB]
    cls = RES['verbs']['table'][verb]
    action, band = stage_for(cls)
    verdict = nre.evaluate(action, band)
    tf = ((idx // PER_VERB) * 13 + (idx % PER_VERB) * 3) % len(TRACE['qpos'])
    # The trace carries a 7-DoF free root (x,y,z + quaternion) followed by joints.
    # Apply ALL of it: replaying only the joints froze the root and made feet float.
    root = TRACE['qpos'][tf][:7]
    d.qpos[0:7] = np.asarray(root, dtype=np.float64)
    for j, name in enumerate(TRACE['joint_names']):
        jid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid >= 0:
            d.qpos[int(m.jnt_qposadr[jid])] = TRACE['qpos'][tf][7 + j]
    for g in range(m.ngeom):
        nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or ''
        if nm.startswith('neon_'):
            p = nm.split('_')
            b = int(p[1]) if len(p) > 1 and p[1].isdigit() else -1
            if 0 <= b < len(nh.BANDS):
                col = nh.BANDS[b][1].lstrip('#')
                rgb = tuple(int(col[k:k+2], 16)/255 for k in (0, 2, 4))
                m.geom_rgba[g] = (*rgb, 1.0 if nh.BANDS[b][0] == band else 0.25)
    # FIXED camera: the root travels 0 -> 1.08 m; following it would hide the motion.
    mujoco.mj_forward(m, d)
    r.disable_segmentation_rendering()
    r.update_scene(d, camera=cam)
    raw = r.render().copy()
    # REAL segmentation: paint only the robot's own geom pixels. No key light.
    r.enable_segmentation_rendering(); r.update_scene(d, camera=cam)
    seg = r.render().copy()
    robot_ids = set()
    for g in range(m.ngeom):
        name = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or ''
        bid = int(m.geom_bodyid[g])
        bname = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, bid) or ''
        if not name.startswith('neon_') and bname != 'world':
            robot_ids.add(g)
    if raw.ndim == 2:
        raw = np.repeat(raw[..., None], 3, axis=2)
    ids = seg[:,:,0]
    void = np.zeros_like(raw) + np.array([0.10,0.09,0.11], dtype=np.float32)
    tube_ids = set(g for g in range(m.ngeom)
                   if (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or '').startswith('neon_'))
    raw = np.where(np.isin(ids, list(tube_ids))[...,None],
                   np.clip(raw * 1.6 + 0.18, 0, 1), void)
    raw[np.isin(ids, list(robot_ids))] = np.array([0.95, 0.72, 0.22], dtype=np.float32)
    rgb = Image.fromarray((np.clip(raw,0,1)*255).astype(np.uint8)).convert('RGB')
    bright = rgb.point(lambda v: v if v > 120 else 0)
    rgb = Image.blend(rgb, bright.filter(ImageFilter.GaussianBlur(3)), 0.22)
    canvas = Image.new('RGB', (W, H), (3,3,5)); canvas.paste(rgb, (0, 64))
    dr = ImageDraw.Draw(canvas)
    dr.rectangle([0,0,W,64], fill=(0,0,0))
    dr.text((14,8), f'æ://NEON ASIMOV · {idx//PER_VERB+1:02d}/{len(VERBS)} · {verb.upper()}',
            font=font(19,True), fill=(212,175,55))
    dr.text((14,38), f'MuJoCo segmentation → neon pixels · no key light needed',
            font=font(12), fill=(112,220,255))
    y0 = 64 + VIEW_H + 10
    col = {'ACCEPT':(0,255,157),'REQUIRE_APPROVAL':(112,220,255),'REFUSE':(255,107,107)}[verdict['decision']]
    dr.text((14,y0), f'{action}/{band} → {verdict["decision"]}', font=font(16,True), fill=col)
    dr.text((14,y0+26), f'trace {RES["trace"]["sha256"][:12]} frame {tf:03d} · policy {verdict["policy_sha256"][:12]}',
            font=font(12), fill=(160,180,190))
    dr.text((14,y0+48), 'NEON BODY · nu=0 · no physical motion · granted:false',
            font=font(13,True), fill=(255,140,140))
    return canvas, {'verb':verb,'class':cls,'decision':verdict['decision'],'trace_frame':tf}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--still',action='store_true'); ap.add_argument('--film',action='store_true')
    a=ap.parse_args()
    ctx=build()
    if a.still:
        import struct
        im,_=frame(2,ctx)
        p=ROOT/'neon-asimov-916.png'; im.save(p)
        b=p.read_bytes()[:24]; w,h=struct.unpack('>II',b[16:24])
        print(json.dumps({'path':str(p),'w':w,'h':h,'ratio':w/h,'bytes':p.stat().st_size,'sha256':sha(p)},indent=2))
        return 0
    dirp=ROOT/'.neon-asimov-frames'; dirp.mkdir(exist_ok=True)
    for p in dirp.glob('f*.png'): p.unlink()
    total=len(VERBS)*PER_VERB
    for i in range(total): frame(i,ctx)[0].save(dirp/f'f{i:05d}.png')
    out=ROOT/'neon-asimov-916.mp4'
    r=subprocess.run([str(FFMPEG),'-y','-framerate',str(FPS),'-i',str(dirp/'f%05d.png'),
        '-c:v','libx264','-pix_fmt','yuv420p','-crf','19','-movflags','+faststart',str(out)],
        capture_output=True,text=True,timeout=600)
    if r.returncode: print(r.stderr[-500:]); return 1
    rec={'schema':'ae/neon-asimov-film/1','artifact':str(out),'bytes':out.stat().st_size,
         'sha256':sha(out),'width':W,'height':H,'ratio':round(W/H,4),'frames':total,
         'duration_s':round(total/FPS,2),'verbs':VERBS,'resources_sha256':sha(ROOT/'NEON-STUDIO-RESOURCES.json'),
         'claim':'all 14 governed verb stages on an emissive Asimov body — no lighting dependency',
         'not_claimed':'physical motion or a grant — nu=0, granted:false',
         'gate':'PENDING — run --gate'}
    rp=out.with_suffix('.receipt.json'); rp.write_text(json.dumps(rec,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(rp),'sha256':rec['sha256'][:16],'frames':total},indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
