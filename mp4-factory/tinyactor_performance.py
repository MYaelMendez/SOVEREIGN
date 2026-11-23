#!/usr/bin/env python3
"""
tinyACTOR performance take — yæl embodying asimov, TRACE REPLAY.

The body is posed from a REAL recorded Menlo qpos trace (216 frames, 25 joints),
not from invented motion and not from a live controller. The film is authorized
by a receipted human-bound take. HUD states the boundary on every frame:
trace replay, nu=0, no commanded act, no physical motion claim.

  python tinyactor_performance.py --board
  python tinyactor_performance.py --film
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, subprocess
from pathlib import Path

import numpy as np

ROOT = Path('C:/æ/mp4-factory')
TRACE = Path('C:/Users/yaelm/AppData/Local/hermes/cache/scratch/asimov-twin/1.0.0/model/physics_trace.json')
W, H = 576, 1024
VIEW_H = 768
FPS = 24
FFMPEG = Path('C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe')
FFPROBE = FFMPEG.with_name('ffprobe.exe')


def _mod(p, n):
    s = importlib.util.spec_from_file_location(n, str(p))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


def font(sz, bold=False):
    from PIL import ImageFont
    p = Path('C:/Windows/Fonts') / ('consolab.ttf' if bold else 'consola.ttf')
    return ImageFont.truetype(str(p), sz) if p.exists() else ImageFont.load_default()


def spec():
    """Refuse without a receipted take — same gate as tinyactor_film."""
    f = _mod('C:/æ/agents/tinyactor_film.py', 'tf_for_perf')
    s = f.bound_spec()
    if not s['ok']:
        return s
    if not TRACE.exists():
        return {'ok': False, 'refused': True, 'reason': 'qpos trace missing'}
    tr = json.loads(TRACE.read_text(encoding='utf-8'))
    return {**s, 'trace_sha256': hashlib.sha256(TRACE.read_bytes()).hexdigest(),
            'trace_frames': tr['frames'], 'trace_nq': tr['nq'],
            'joint_names': tr['joint_names'], 'qpos': tr['qpos']}


def build(sp):
    import mujoco
    nh = _mod(ROOT/'neon_holomesh.py', 'nh_for_perf')
    m = mujoco.MjModel.from_xml_string(nh.build_xml())
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    r = mujoco.Renderer(m, height=VIEW_H, width=W)
    r.update_scene(d); r.render()
    cam = mujoco.MjvCamera()
    cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    cam.azimuth, cam.elevation, cam.distance = 180.0, -8.0, 3.3
    cam.lookat = np.array([0.0, 0.0, 1.05])
    return mujoco, m, d, r, cam, nh


def frame(i, sp, ctx):
    mujoco, m, d, r, cam, nh = ctx
    from PIL import Image, ImageDraw, ImageFilter
    qi = i % sp['trace_frames']
    for j, name in enumerate(sp['joint_names']):
        jid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid >= 0:
            d.qpos[int(m.jnt_qposadr[jid])] = sp['qpos'][qi][j]
    mujoco.mj_forward(m, d)
    # active authority band cycles with the take scene
    active = (i // 18) % 4
    for g in range(m.ngeom):
        nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, g) or ''
        if nm.startswith('neon_'):
            b = int(nm.split('_')[1]) if nm.split('_')[1].isdigit() else -1
            if b >= 0:
                col = nh.BANDS[b][1].lstrip('#')
                rgb = tuple(int(col[k:k+2], 16)/255 for k in (0, 2, 4))
                m.geom_rgba[g] = (*rgb, 1.0 if b == active else 0.3)
    mujoco.mj_forward(m, d)
    r.update_scene(d, camera=cam)
    img = Image.fromarray(r.render()).convert('RGB')
    bright = img.point(lambda v: v if v > 90 else 0)
    img = Image.blend(img, bright.filter(ImageFilter.GaussianBlur(8)), 0.35)
    canvas = Image.new('RGB', (W, H), (3,3,5)); canvas.paste(img, (0, 64))
    dr = ImageDraw.Draw(canvas)
    dr.rectangle([0,0,W,64], fill=(0,0,0))
    dr.text((14,8), 'æ://tinyACTOR · yæl → asimov', font=font(21, True), fill=(212,175,55))
    dr.text((14,38), f'TRACE REPLAY frame {qi+1}/{sp["trace_frames"]} · take {sp["take_sha256"][:12]}',
            font=font(12), fill=(140,200,210))
    y0 = 64 + VIEW_H + 12
    dr.text((14,y0), 'TRAINED TRACE · NOT LIVE CONTROL', font=font(15, True), fill=(0,255,157))
    dr.text((14,y0+26), 'nu=0 · no commanded act · no physical motion claim',
            font=font(12), fill=(255,140,140))
    dr.text((14,y0+48), f'op {sp["operator"]} · body {sp["actor"]} · granted:false',
            font=font(12), fill=(160,180,190))
    return canvas


def gate(path):
    out = ROOT/'.tinyactor-perf-decode'; out.mkdir(exist_ok=True)
    for p in out.glob('*.png'): p.unlink()
    r=subprocess.run([str(FFMPEG),'-v','error','-i',str(path),str(out/'d%04d.png')],capture_output=True,text=True,timeout=240)
    if r.returncode: return {'ok':False,'refused':True,'reason':'decode failed'}
    import numpy as np
    from PIL import Image
    files=sorted(out.glob('*.png')); ims=[np.asarray(Image.open(p).convert('L'),dtype=np.float32) for p in files[::12]]
    lum=min(float(x.mean()) for x in ims); con=min(float(x.std()) for x in ims)
    mot=max(float(np.abs(ims[i].astype(int)-ims[i-1].astype(int)).mean()) for i in range(1,len(ims)))
    checks={'lum_ok':lum>20,'contrast_ok':con>10,'motion_ok':mot>0.5,'frames_ok':len(files)>0}
    return {'ok':all(checks.values()),'checks':checks,'decoded_frames':len(files),
            'luminance_min':round(lum,2),'contrast_min':round(con,2),'motion_max':round(mot,3)}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--board',action='store_true'); ap.add_argument('--film',action='store_true')
    a=ap.parse_args(); sp=spec()
    if not sp['ok']:
        print(json.dumps(sp,indent=2,ensure_ascii=False)); return 1
    print('performance authorized by take',sp['take_sha256'][:16],'trace',sp['trace_sha256'][:16])
    ctx=build(sp)
    if a.board:
        from PIL import Image
        cells=[]
        for k in range(4):
            im=frame(k*18+2,sp,ctx); im.thumbnail((288,512)); cells.append(im.copy())
        sheet=Image.new('RGB',(1152,512),(0,0,0))
        for i,im in enumerate(cells): sheet.paste(im,(i*288,0))
        p=ROOT/'tinyactor-performance-board.png'; sheet.save(p)
        print('board',p.stat().st_size,'B'); return 0
    dirp=ROOT/'.tinyactor-perf-frames'; dirp.mkdir(exist_ok=True)
    for p in dirp.glob('f*.png'): p.unlink()
    total=sp['trace_frames']
    for i in range(total): frame(i,sp,ctx).save(dirp/f'f{i:05d}.png')
    out=ROOT/'tinyactor-performance-916.mp4'
    cmd=[str(FFMPEG),'-y','-framerate',str(FPS),'-i',str(dirp/'f%05d.png'),'-c:v','libx264',
         '-pix_fmt','yuv420p','-crf','19','-movflags','+faststart',str(out)]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
    if r.returncode: print(r.stderr[-500:]); return 1
    g=gate(out)
    rec={'schema':'ae/tinyactor-performance/1','artifact':str(out),'bytes':out.stat().st_size,
      'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'width':W,'height':H,'ratio':round(W/H,4),
      'frames':total,'duration_s':round(total/FPS,2),'take_sha256':sp['take_sha256'],
      'trace_sha256':sp['trace_sha256'],'operator':sp['operator'],'actor':sp['actor'],
      'gate':g,'granted':False,'grants':False,
      'claim':'yæl embodying asimov by TRACE REPLAY under a receipted take',
      'not_claimed':'live control, commanded act, or physical motion — nu=0 plant'}
    rp=out.with_suffix('.receipt.json'); rp.write_text(json.dumps(rec,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('FILM',rec['sha256'][:20],'GATE',g); return 0


if __name__=='__main__': raise SystemExit(main())
