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
    ap.add_argument('--cast', help='comma-separated member ids for N bodies, e.g. nous,hermes,menlo,asimov')
    ap.add_argument('--trace', help='tinyPython locomotion trace — the legs walk, they are not keyed')
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
    IDS = [s.strip() for s in a.cast.split(',')] if a.cast else [a.left, a.right]
    MEMBERS = [cast[i] for i in IDS]
    NB = len(MEMBERS)
    L, R = MEMBERS[0], MEMBERS[-1]
    chassis = np.array([0.78, 0.78, 0.80], np.float32)
    # two colour tables, concatenated: body 0 uses 0..nL-1, body 1 uses nL..2nL-1
    def table(rgb):
        return np.array([[c / 255.0 for c in rgb] if n == 'neck_pitch_link' else chassis
                         for n in names], np.float32)
    cols = np.concatenate([table(m['head_rgb']) for m in MEMBERS])
    print('  cast: ' + '  '.join(f'{i}{m["head_rgb"]}' for i, m in zip(IDS, MEMBERS)))

    # the policy gait, if given: real qpos from Menlo's ONNX against contact
    TR = None
    if a.trace:
        _td = json.loads(Path(a.trace).read_text(encoding='utf-8'))
        _jn = _td['joint_names']
        TR = {'names': _jn, 'q': np.array(_td['qpos'], np.float32)[:, 7:7+len(_jn)],
              'n': len(_td['qpos']), 'travel': _td.get('base_x')}
        print(f'  GAIT: policy trace {TR["n"]} frames · travel {TR["travel"]:.3f} m')

    V0, N0, _ = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    zmin, zmax = float(V0[:, :, 2].min()), float(V0[:, :, 2].max())
    lift = -zmin
    span = zmax - zmin
    W, H = 720, 1280
    HDR, HUD = 92, 900
    VH = HUD - HDR
    P = persp(38.0, 0.05, 80.0, aspect=W / VH)
    ctr = np.array([0, 0, span * 0.52], np.float32)
    dist = span * (2.75 + 0.62 * max(0, NB - 2))

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
    # derived is a fact about the cast, not a caption to hard-code. nous and
    # hermes are the base voices; waetz, menlo and asimov are personas on them.
    _dl, _dr = bool(L.get('derived')), bool(R.get('derived'))
    if not _dl and not _dr:
        _derived_line = 'both derived:false — the base voices'
    elif _dl and _dr:
        _derived_line = 'both derived:true — personas on the base voices'
    else:
        _derived_line = f'{a.left} derived:{str(_dl).lower()} · {a.right} derived:{str(_dr).lower()}'

    def body(root, offset, phase=0.0):
        ang = {}
        if TR is not None:
            # each body enters the gait at a different phase, so they are not
            # marching in lockstep — the policy is the same, the timing is not
            k = int((phase * TR['n'])) % TR['n']
            ang = {nm: float(TR['q'][k, j]) for j, nm in enumerate(TR['names'])}
        V, N, Li = ra.world_tris(links, ra.transforms(urdf, ang), root)
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
        sep = (1.0 - ease) * span * 0.95 + span * 0.34
        tt = i / a.fps
        sway = 0.05 * math.sin(tt * 1.7)

        roots = []
        for bi in range(NB):
            # spread across Y, evenly, converging on the centre
            frac = (bi - (NB - 1) / 2.0) / max(1, (NB - 1) / 2.0)
            sgn = 1 if frac >= 0 else -1
            M = np.eye(4, dtype=np.float32)
            yaw = -sgn * (math.pi / 2) * (1.0 - 0.62 * ease) + sway
            M[:3, :3] = ra.rot_euler([0, 0, yaw])
            M[1, 3] = frac * sep * (NB - 1) * 0.24
            M[2, 3] = lift + 0.02 * math.sin(tt * 1.9 + bi)
            roots.append(M)

        Vs, Ns, Ls = [], [], []
        for bi, root in enumerate(roots):
            # advance through the gait while converging, offset per body
            ph = (u * 1.6 + bi * 0.17) % 1.0
            vv, nn, ll = body(root, bi * nL, ph)
            Vs.append(vv); Ns.append(nn); Ls.append(ll)
        V = np.concatenate(Vs); N = np.concatenate(Ns); Li = np.concatenate(Ls)

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
        for bi, m in enumerate(MEMBERS):
            x0 = int(W * bi / NB); x1 = int(W * (bi + 1) / NB)
            d.rectangle([x0, HUD, x1, HUD + 5], fill=(*m['head_rgb'], 255))
        y = HUD + 22
        _lines = [f'{i}  ·  {m.get("role", "")}' for i, m in zip(IDS, MEMBERS)]
        _lines.append(f'{len(V):,} triangles · {NB} bodies · one frame')
        _lines.append(_derived_line if NB == 2 else
                      f'{sum(1 for m in MEMBERS if m.get("derived"))} derived · '
                      f'{sum(1 for m in MEMBERS if not m.get("derived"))} base · one signature')
        if TR is not None:
            _lines.append('gait: Menlo ONNX policy · not keyframed')
        for ln in _lines[:6]:
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
            _need = int(math.ceil(total * a.fps))
            if _need > nf:
                print(f'  AUDIO {total:.2f}s needs {_need} frames, had {nf} — extending')
                for i in range(nf, _need):
                    u2 = i / max(1, _need - 1)
                    e2 = min(1.0, u2 / 0.72); ease2 = e2*e2*(3-2*e2)
                    sep2 = (1.0 - ease2) * span * 0.95 + span * 0.34
                    tt2 = i / a.fps; sway2 = 0.05 * math.sin(tt2 * 1.7)
                    Vs2, Ns2, Ls2 = [], [], []
                    for bi in range(NB):
                        frac = (bi - (NB-1)/2.0) / max(1, (NB-1)/2.0)
                        sgn = 1 if frac >= 0 else -1
                        M = np.eye(4, dtype=np.float32)
                        M[:3, :3] = ra.rot_euler([0, 0, -sgn*(math.pi/2)*(1.0-0.62*ease2)+sway2])
                        M[1, 3] = frac * sep2 * (NB-1) * 0.24
                        M[2, 3] = lift + 0.02*math.sin(tt2*1.9 + bi)
                        ph = (u2*1.6 + bi*0.17) % 1.0
                        vv, nn, ll = body(M, bi*nL, ph)
                        Vs2.append(vv); Ns2.append(nn); Ls2.append(ll)
                    V2 = np.concatenate(Vs2); N2 = np.concatenate(Ns2); L2 = np.concatenate(Ls2)
                    az2 = 0.18*math.sin(tt2*0.5)
                    eye2 = ctr + np.array([dist*math.cos(az2), dist*math.sin(az2),
                                           0.18+0.06*math.sin(tt2*0.8)], np.float32)
                    px2 = r.render(V2, N2, cols[L2], P @ look_at(eye2, ctr))
                    cv2_ = Image.new('RGB', (W, H), (11, 10, 6))
                    cv2_.paste(Image.fromarray(px2), (0, HDR))
                    d2 = ImageDraw.Draw(cv2_, 'RGBA')
                    d2.rectangle([0, 0, W, HDR], fill=(212, 175, 55, 255))
                    d2.text((26, 14), a.title, font=F_B, fill=(11, 10, 6, 255))
                    d2.text((26, 54), a.tagline, font=F_S, fill=(58, 48, 16, 255))
                    d2.rectangle([0, HUD, W, H], fill=(14, 13, 8, 255))
                    for bi, m in enumerate(MEMBERS):
                        x0 = int(W*bi/NB); x1 = int(W*(bi+1)/NB)
                        d2.rectangle([x0, HUD, x1, HUD+5], fill=(*m['head_rgb'], 255))
                    _y = HUD + 22
                    _l2 = [f'{i_}  ·  {m.get("role","")}' for i_, m in zip(IDS, MEMBERS)]
                    _l2.append(f'{len(V2):,} triangles · {NB} bodies · one frame')
                    _l2.append(_derived_line if NB == 2 else
                               f'{sum(1 for m in MEMBERS if m.get("derived"))} derived · '
                               f'{sum(1 for m in MEMBERS if not m.get("derived"))} base · one signature')
                    if TR is not None:
                        _l2.append('gait: Menlo ONNX policy · not keyframed')
                    for ln in _l2[:6]:
                        d2.text((26, _y), ln, font=F_S, fill=(255, 246, 218, 255)); _y += 30
                    d2.text((26, H-40), 'RTX:// CUDA · HUMAN://ROOT · one signature',
                            font=F_X, fill=(138, 122, 63, 255))
                    cv2_.save(fd / f'f{i:05d}.png')
                nf = _need
                subprocess.run([str(ff/'ffmpeg'), '-v', 'error', '-y', '-framerate', str(a.fps),
                                '-i', str(fd/'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                                '-pix_fmt', 'yuv420p', str(silent)],
                               capture_output=True, timeout=3600)
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
            'raster_ms': round(rms / nf, 1), 'bodies': NB,
            'cast': {i: m['head_rgb'] for i, m in zip(IDS, MEMBERS)},
            'gait': ('policy' if TR is not None else 'static'),
            'links_per_body': nL, 'triangles': int(len(V)),
            'device': 'RTX 3050 CUDA', 'bytes': out.stat().st_size,
            'authority': 'HUMAN://ROOT', 'grants': False}
    (wd / 'convergence.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta))


if __name__ == '__main__':
    main()
