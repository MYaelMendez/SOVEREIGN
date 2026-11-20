#!/usr/bin/env python3
"""convergence — two cast members, one frame, one authority.

nous girl (F2, magenta) and hermes-agent (M2, cyan) are the two BASE voices:
`derived: false` in cast.json. The other three are personas built on them.
This renders the two roots converging.

    python convergence.py --out film.mp4 --seconds 5

Two bodies means two root transforms and an OFFSET link-index table — the
second body's triangles must index the second half of the colour buffer, or
both robots wear the first one's head.

Everything else is the same chain: tinyCUDA rasterises, tiny-voca speaks,
the sound world beds under it, the gate decides, the receipt proves.

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _ffmpeg() -> Path:
    h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    p = h / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
    if p.exists():
        return p
    import shutil
    w = shutil.which('ffmpeg')
    if not w:
        raise SystemExit('ffmpeg not found')
    return Path(w).parent


def load_cast() -> dict:
    h = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes'))
    p = h / 'plugins' / 'hermes-asimov' / 'cast.json'
    if not p.exists():
        raise SystemExit(f'cast.json not found at {p}')
    d = json.loads(p.read_text(encoding='utf-8'))
    return {m['id']: m for m in d.get('cast', [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--seconds', type=float, default=5.0)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--left', default='nous')
    ap.add_argument('--right', default='hermes')
    ap.add_argument('--title', default='convergence')
    ap.add_argument('--tagline', default='TWO VOICES · ONE SIGNATURE')
    ap.add_argument('--scenes')
    ap.add_argument('--texture', default='sci_fi')
    ap.add_argument('--silent', action='store_true')
    a = ap.parse_args()

    import importlib.util
    spec = importlib.util.spec_from_file_location('ra', HERE / 'rtx_asimov.py')
    ra = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ra)

    from tinycuda import Raster, persp, look_at

    MD = Path(a.model_dir)
    urdf = json.loads((MD / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = MD / 'meshes'
    links = ra.load_links(urdf)
    names = list(links.keys())
    nL = len(names)
    print(f'  {nL} links per body · {sum(len(v) for v, _ in links.values()):,} tris per body')

    cast = load_cast()
    L, R = cast[a.left], cast[a.right]
    chassis = np.array([0.78, 0.78, 0.80], np.float32)
    # two colour tables, concatenated: body 0 uses 0..nL-1, body 1 uses nL..2nL-1
    def table(rgb):
        return np.array([[c / 255.0 for c in rgb] if n == 'neck_pitch_link' else chassis
                         for n in names], np.float32)
    cols = np.concatenate([table(L['head_rgb']), table(R['head_rgb'])])
    print(f'  {a.left} {L["head_rgb"]}  +  {a.right} {R["head_rgb"]}')

    V0, N0, _ = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    zmin, zmax = float(V0[:, :, 2].min()), float(V0[:, :, 2].max())
    lift = -zmin
    span = zmax - zmin
    W, H = 720, 1280
    HDR, HUD = 92, 900
    VH = HUD - HDR
    P = persp(38.0, 0.05, 80.0, aspect=W / VH)
    ctr = np.array([0, 0, span * 0.52], np.float32)
    dist = span * 2.75

    r = Raster(W, VH)
    nf = int(round(a.seconds * a.fps))
    out = Path(a.out)
    wd = out.parent / (out.stem + '-conv')
    fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)

    def font(sz, bold=False):
        try:
            return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if bold
                                      else 'C:/Windows/Fonts/consola.ttf', sz)
        except Exception:
            return ImageFont.load_default()
    F_B, F_S, F_X = font(30, True), font(19), font(17)

    def body(root, offset):
        V, N, Li = ra.world_tris(links, ra.transforms(urdf, {}), root)
        return V, N, Li + offset

    # warmup — the first render is a JIT artifact, never a published frame
    v0, n0, l0 = body(np.eye(4), 0)
    r.render(v0, n0, cols[l0], P @ look_at(ctr + [dist, 0, 0.15], ctr))

    t0 = time.time()
    rms = 0.0
    for i in range(nf):
        u = i / max(1, nf - 1)                 # 0..1 across the film
        # converge: start wide apart, meet at the centre, hold
        e = min(1.0, u / 0.72)
        ease = e * e * (3 - 2 * e)             # smoothstep
        sep = (1.0 - ease) * span * 0.95 + span * 0.30
        tt = i / a.fps
        sway = 0.05 * math.sin(tt * 1.7)

        roots = []
        for sgn in (-1, 1):
            M = np.eye(4, dtype=np.float32)
            # face each other: yaw inward, plus a small breathing motion
            # face each other across Y: the left body turns +90deg, the right
            # -90deg, easing toward a shared forward stance as they meet
            yaw = -sgn * (math.pi / 2) * (1.0 - 0.55 * ease) + sway
            M[:3, :3] = ra.rot_euler([0, 0, yaw])
            M[1, 3] = sgn * sep * 0.5      # across the image plane, not into it
            M[2, 3] = lift + 0.02 * math.sin(tt * 1.9 + sgn)
            roots.append(M)

        Va, Na, La = body(roots[0], 0)
        Vb, Nb, Lb = body(roots[1], nL)
        V = np.concatenate([Va, Vb]); N = np.concatenate([Na, Nb])
        Li = np.concatenate([La, Lb])

        az = 0.18 * math.sin(tt * 0.5)
        eye = ctr + np.array([dist * math.cos(az), dist * math.sin(az),
                              0.18 + 0.06 * math.sin(tt * 0.8)], np.float32)
        tr = time.time()
        img = r.render(V, N, cols[Li], P @ look_at(eye, ctr))
        rms += (time.time() - tr) * 1000

        cv = Image.new('RGB', (W, H), (11, 10, 6))
        cv.paste(Image.fromarray(img), (0, HDR))
        d = ImageDraw.Draw(cv, 'RGBA')
        d.rectangle([0, 0, W, HDR], fill=(212, 175, 55, 255))
        d.text((26, 14), a.title, font=F_B, fill=(11, 10, 6, 255))
        d.text((26, 54), a.tagline, font=F_S, fill=(58, 48, 16, 255))
        d.rectangle([0, HUD, W, H], fill=(14, 13, 8, 255))
        # the accent bar carries BOTH identities, split down the middle
        d.rectangle([0, HUD, W // 2, HUD + 5], fill=(*L['head_rgb'], 255))
        d.rectangle([W // 2, HUD, W, HUD + 5], fill=(*R['head_rgb'], 255))
        y = HUD + 22
        for ln in [f'{a.left}  ·  {L.get("role", "")}',
                   f'{a.right}  ·  {R.get("role", "")}',
                   f'{len(V):,} triangles · two bodies · one frame',
                   'both derived:false — the base voices']:
            d.text((26, y), ln, font=F_S, fill=(255, 246, 218, 255)); y += 30
        d.text((26, H - 40), 'RTX:// CUDA · HUMAN://ROOT · one signature',
               font=F_X, fill=(138, 122, 63, 255))
        cv.save(fd / f'f{i:05d}.png')
        if i % 24 == 0:
            print(f'  {i}/{nf}')

    el = time.time() - t0
    print(f'  {nf} frames in {el:.1f}s ({el/nf*1000:.0f} ms/frame, {rms/nf:.1f} ms raster)')
    ff = _ffmpeg()
    silent = wd / 'silent.mp4'
    subprocess.run([str(ff / 'ffmpeg'), '-v', 'error', '-y', '-framerate', str(a.fps),
                    '-i', str(fd / 'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                    '-pix_fmt', 'yuv420p', str(silent)], check=True, capture_output=True, timeout=1800)

    audio = {'voice': False, 'world': False}
    if not a.silent and a.scenes:
        scenes = json.loads(Path(a.scenes).read_text(encoding='utf-8'))['scenes']
        tts = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes')) / \
            'plugins' / 'tiny-voca-voice' / 'scripts' / 'tiny_voca_voice.py'
        wavs = []
        if tts.exists():
            for i, sc in enumerate(scenes):
                w = wd / f's{i}.wav'
                subprocess.run([sys.executable, str(tts), '--text', sc.get('speak', ''),
                                '--voice', sc.get('voice', 'M2'), '--output', str(w)],
                               capture_output=True, timeout=300)
                if w.exists():
                    wavs.append(w)
            audio['voice'] = bool(wavs) and len(wavs) == len(scenes)
        if wavs:
            lst = wd / 'audio.txt'
            lst.write_text(''.join(f"file '{w.as_posix()}'\n" for w in wavs), encoding='utf-8')
            track = wd / 'track.wav'
            subprocess.run([str(ff / 'ffmpeg'), '-v', 'error', '-y', '-f', 'concat', '-safe', '0',
                            '-i', str(lst), '-ar', '24000', '-ac', '1', str(track)],
                           capture_output=True, timeout=600)
            total = max(track.stat().st_size / 48000.0, nf / float(a.fps))
            subprocess.run([str(ff / 'ffmpeg'), '-v', 'error', '-y', '-i', str(silent),
                            '-i', str(track), '-c:v', 'copy',
                            '-filter:a', f'apad=whole_dur={total:.6f}',
                            '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
                            '-t', f'{total:.6f}', str(out)], capture_output=True, timeout=900)
            try:
                import sound_link as S
                t0s = 0.0
                for sc, w in zip(scenes, wavs):
                    d_ = w.stat().st_size / 48000.0
                    sc['_t0'] = t0s; sc['_dur'] = d_; t0s += d_
                a_ = S.spec_from_film({'scenes': scenes, '_total': t0s},
                                      texture=a.texture, bed_db=-29.0)
                wv = wd / 'world.wav'
                rr = S.render(a_, wv)
                if rr.get('ok'):
                    mixed = wd / 'world.mp4'
                    if S.mix(out, wv, mixed, bed_gain=0.5).get('ok'):
                        mixed.replace(out)
                        audio['world'] = True
                        audio['events'] = len(a_['events'])
                        audio['torch'] = rr.get('torch')
            except Exception as exc:
                print(f'  world stage: {type(exc).__name__}: {exc}')
    if not out.exists():
        silent.replace(out)

    meta = {'audio': audio, 'frames': nf, 'fps': a.fps, 'seconds': round(el, 1),
            'raster_ms': round(rms / nf, 1), 'bodies': 2,
            'cast': {a.left: L['head_rgb'], a.right: R['head_rgb']},
            'links_per_body': nL, 'triangles': int(len(V)),
            'device': 'RTX 3050 CUDA', 'bytes': out.stat().st_size,
            'authority': 'HUMAN://ROOT', 'grants': False}
    (wd / 'convergence.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta))


if __name__ == '__main__':
    main()
