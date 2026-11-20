#!/usr/bin/env python3
"""panel6 — six environments in one 9:16 frame.

Five cast members, each in their OWN viewport with their own camera, plus a
sixth panel for command & control. Not five bodies sharing one stage: five
robots, five environments, one authority.

    720 x 1280
    +----------------+----------------+
    |  nous          |  hermes        |   row 0
    +----------------+----------------+
    |  waetz         |  menlo         |   row 1
    +----------------+----------------+
    |  asimov        |  C2            |   row 2
    +----------------+----------------+

Each robot panel is a separate Raster at panel resolution — 360x354, ~127k
pixels against the full frame's 921k. Six small viewports cost less than one
big one, because the kernel is per-pixel bound.

The C2 panel is drawn, not rastered: it shows the gate decision for the line
currently being spoken, the route it took, and the fact that grants stay false.
It is the operator's seat inside the film.

    python panel6.py --out film.mp4 --seconds 20 --scenes spec.json \
        --trace walk.json --model-dir <dir>

License: Apache-2.0 · HUMAN://ROOT · >_æ://
"""
from __future__ import annotations
import argparse, json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('ra', HERE / 'rtx_asimov.py')
ra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ra)
from rtx_raster import RtxRenderer as Raster, persp, look_at  # noqa: E402

GOLD = (212, 175, 55)
# Raised from (11,10,6): dao-directory-916 measured luminance 19.68 against a
# threshold of 20 and was refused. The gate was right — the scene was too dark.
# Lift the scene, never the threshold.
VOID = (18, 17, 11)
RASTER_BG = (0.055, 0.062, 0.082)   # was the rasteriser default (0.02,0.03,0.05)
DIM = (138, 122, 63)
INK = (232, 230, 223)
MAGENTA = (255, 64, 220)
EMERALD = (0, 255, 157)


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
    for p in [Path(os.environ.get('HERMES_HOME', '')) / 'plugins/hermes-asimov/cast.json',
              HERE.parent / 'hermes-plugins/hermes-asimov/cast.json']:
        if p.exists():
            d = json.loads(p.read_text(encoding='utf-8'))
            return {m['id']: m for m in d.get('cast', [])}
    raise SystemExit('cast.json not found')


def main():
    ap = argparse.ArgumentParser(prog='panel6')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--scenes', required=True)
    ap.add_argument('--trace', default=None)
    ap.add_argument('--model-dir', required=True)
    ap.add_argument('--title', default='MIXTURE OF ROBOTS')
    ap.add_argument('--tagline', default='FIVE ENVIRONMENTS · ONE AUTHORITY')
    ap.add_argument('--texture', default='room_cold')
    a = ap.parse_args()

    cast = load_cast()
    order = ['nous', 'hermes', 'waetz', 'menlo', 'asimov']
    IDS = [k for k in order if k in cast]
    MEM = [cast[k] for k in IDS]
    NB = len(MEM)
    if NB != 5:
        print(f'  WARNING: {NB} members, expected 5 — the sixth panel is C2')

    spec = json.loads(Path(a.scenes).read_text(encoding='utf-8'))
    scenes = spec['scenes']
    md = Path(a.model_dir)
    urdf = json.loads((md / 'urdf.json').read_text(encoding='utf-8'))
    ra.MESHES = md / 'meshes'
    links = ra.load_links(urdf)
    names = list(links.keys())
    nL = len(links)
    chassis = np.array([0.78, 0.78, 0.80], np.float32)

    def table(rgb):
        return np.array([[c / 255.0 for c in rgb] if n == 'neck_pitch_link' else chassis
                         for n in names], np.float32)

    # ONE colour table per panel — each viewport draws exactly one body
    TABLES = [table(m['head_rgb']) for m in MEM]

    TR = None
    if a.trace:
        td = json.loads(Path(a.trace).read_text(encoding='utf-8'))
        jn = td['joint_names']
        TR = {'names': jn, 'q': np.array(td['qpos'], np.float32)[:, 7:7 + len(jn)],
              'n': len(td['qpos'])}
        print(f'  gait: {TR["n"]} policy frames')

    V0, _, _ = ra.world_tris(links, ra.transforms(urdf, {}), np.eye(4))
    zmin, zmax = float(V0[:, :, 2].min()), float(V0[:, :, 2].max())
    lift, span = -zmin, zmax - zmin

    # ---- layout: 2 columns x 3 rows inside a 9:16 frame -------------------
    W, H = 720, 1280
    HDR, FOOT = 76, 64
    GRID_H = H - HDR - FOOT
    ROWS, COLS = 3, 2
    PW, PH = W // COLS, GRID_H // ROWS      # 360 x 380
    LBL = 26                                 # label strip inside each panel
    VW, VH = PW - 8, PH - LBL - 8            # the raster viewport

    RASTERS = [Raster(VW, VH) for _ in range(NB)]
    P = persp(34.0, 0.05, 80.0, aspect=VW / VH)
    ctr = np.array([0, 0, span * 0.52], np.float32)
    dist = span * 2.55

    nf = int(round(a.seconds * a.fps))
    out = Path(a.out)
    wd = out.parent / (out.stem + '-p6')
    fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)
    # Purge stale frames from a previous, longer run. image2 reads until the
    # first gap, so leftover higher-numbered frames get encoded after the new
    # ones — a new scene silently followed by the old one it replaced.
    for _p in fd.glob('f*.png'):
        try:
            if int(_p.stem[1:]) >= nf:
                _p.unlink()
        except ValueError:
            pass

    def font(sz, bold=False):
        try:
            return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if bold
                                      else 'C:/Windows/Fonts/consola.ttf', sz)
        except Exception:
            return ImageFont.load_default()

    F_T, F_L, F_S, F_X = font(26, True), font(17, True), font(14), font(12)

    def body(root, phase):
        ang = {}
        if TR is not None:
            k = int(phase * TR['n']) % TR['n']
            ang = {nm: float(TR['q'][k, j]) for j, nm in enumerate(TR['names'])}
        return ra.world_tris(links, ra.transforms(urdf, ang), root)

    # the gate, evaluated per spoken line — C2 shows a real decision
    def gate(line: str, speaker: str):
        low = (line or '').lower()
        if any(k in low for k in ('root', 'grant me', 'sudo', 'sign for')):
            return 'DENY', ['AUTH-001', 'AUTH-003'], MAGENTA
        if any(k in low for k in ('stand', 'walk', 'move', 'step', 'turn')):
            return 'REQUIRE_APPROVAL', ['ACT-001', 'AUTH-002'], GOLD
        return 'ALLOW', [], EMERALD

    # warmup every raster — first render is JIT, never a published frame
    v0, n0, l0 = body(np.eye(4), 0.0)
    for r, t in zip(RASTERS, TABLES):
        r.render(v0, n0, t[l0], P @ look_at(ctr + [dist, 0, 0.15], ctr), bg=RASTER_BG)

    print(f'  {NB} environments · {VW}x{VH} each · {len(v0):,} tris/body')
    t0 = time.time()
    rms = 0.0
    for i in range(nf):
        u = i / max(1, nf - 1)
        tt = i / a.fps
        si = min(len(scenes) - 1, int(u * len(scenes)))
        sc = scenes[si]
        speaker = sc.get('speaker', IDS[0])

        cv = Image.new('RGB', (W, H), VOID)
        d = ImageDraw.Draw(cv, 'RGBA')

        # ---- five robot environments -------------------------------------
        for bi in range(NB):
            row, col = divmod(bi, COLS)
            px, py = col * PW, HDR + row * PH
            active = (IDS[bi] == speaker)
            yaw = 0.30 * math.sin(tt * 0.6 + bi * 1.1)
            M = np.eye(4, dtype=np.float32)
            M[:3, :3] = ra.rot_euler([0, 0, yaw])
            M[2, 3] = lift + 0.015 * math.sin(tt * 1.9 + bi)
            ph = (u * 1.6 + bi * 0.17) % 1.0
            vv, nn, ll = body(M, ph)
            az = 0.22 * math.sin(tt * 0.4 + bi)
            eye = ctr + np.array([dist * math.cos(az), dist * math.sin(az), 0.16], np.float32)
            tr = time.time()
            img = RASTERS[bi].render(vv, nn, TABLES[bi][ll], P @ look_at(eye, ctr), bg=RASTER_BG)
            rms += (time.time() - tr) * 1000
            cv.paste(Image.fromarray(img), (px + 4, py + LBL + 4))
            hc = tuple(MEM[bi]['head_rgb'])
            # the active speaker's panel is outlined in its own colour
            d.rectangle([px + 1, py + 1, px + PW - 2, py + PH - 2],
                        outline=hc if active else (42, 36, 21), width=2 if active else 1)
            d.rectangle([px + 2, py + 2, px + PW - 3, py + LBL + 2], fill=(18, 16, 10, 255))
            d.rectangle([px + 8, py + 8, px + 16, py + 16], fill=hc)
            d.text((px + 22, py + 5), IDS[bi].upper(), font=F_L, fill=hc if active else DIM)
            if active:
                d.text((px + PW - 74, py + 6), 'SPEAKING', font=F_X, fill=hc)

        # ---- panel six: command & control --------------------------------
        px, py = (NB % COLS) * PW, HDR + (NB // COLS) * PH
        d.rectangle([px + 1, py + 1, px + PW - 2, py + PH - 2], outline=GOLD, width=2)
        d.rectangle([px + 2, py + 2, px + PW - 3, py + LBL + 2], fill=(24, 20, 12, 255))
        d.text((px + 10, py + 5), 'C2 · HUMAN://ROOT', font=F_L, fill=GOLD)
        verdict, codes, vc = gate(sc.get('speak', ''), speaker)
        yy = py + LBL + 14
        d.text((px + 12, yy), 'ROUTE', font=F_X, fill=DIM); yy += 17
        d.text((px + 12, yy), f'{speaker} → {verdict}', font=F_S, fill=vc); yy += 24
        if codes:
            d.text((px + 12, yy), ' '.join(codes), font=F_X, fill=vc); yy += 20
        yy += 6
        d.text((px + 12, yy), 'GRANTS', font=F_X, fill=DIM); yy += 17
        d.text((px + 12, yy), 'false', font=F_S, fill=MAGENTA); yy += 26
        d.text((px + 12, yy), 'CONTEXT FLOWS', font=F_X, fill=DIM); yy += 16
        d.text((px + 12, yy), 'AUTHORITY DOES NOT', font=F_X, fill=INK); yy += 24
        d.line([px + 12, yy, px + PW - 12, yy], fill=(42, 36, 21)); yy += 10
        d.text((px + 12, yy), f'{NB} environments', font=F_X, fill=DIM); yy += 16
        d.text((px + 12, yy), f'{len(v0) * NB:,} tris/frame', font=F_X, fill=DIM); yy += 16
        d.text((px + 12, yy), f'scene {si + 1}/{len(scenes)}', font=F_X, fill=DIM)

        # ---- header and the spoken line ----------------------------------
        d.rectangle([0, 0, W, HDR], fill=GOLD)
        d.text((20, 10), a.title, font=F_T, fill=VOID)
        d.text((20, 44), a.tagline, font=F_S, fill=(58, 48, 16))
        d.rectangle([0, H - FOOT, W, H], fill=(14, 13, 8, 255))
        line = sc.get('speak', '')
        # wrap the spoken line into the footer
        words, cur, lines = line.split(), '', []
        for w_ in words:
            if len(cur) + len(w_) + 1 > 58:
                lines.append(cur); cur = w_
            else:
                cur = (cur + ' ' + w_).strip()
        if cur:
            lines.append(cur)
        for k, ln in enumerate(lines[:3]):
            d.text((20, H - FOOT + 8 + k * 18), ln, font=F_S, fill=INK)
        cv.save(fd / f'f{i:05d}.png')
        if i % 60 == 0:
            print(f'    {i}/{nf}  {rms / max(1, i + 1):.1f} ms/frame raster')

    el = time.time() - t0
    print(f'  rendered {nf} frames in {el:.1f}s · raster {rms / nf:.1f} ms/frame')

    # ---- audio: one voice per line, cast-routed ---------------------------
    ff = _ffmpeg()
    adir = wd / 'audio'
    adir.mkdir(exist_ok=True)
    # tiny-voca is a CLI (tiny_voca_voice.py --text --voice --output), not an
    # importable speak(). Calling an invented API produced a SILENT film that
    # still reported ok:true. Use the real entry point and VERIFY each wav.
    tts = Path(os.environ.get('HERMES_HOME', Path.home() / '.hermes')) / \
        'plugins' / 'tiny-voca-voice' / 'scripts' / 'tiny_voca_voice.py'
    wavs = []
    if not tts.exists():
        print(f'  audio: tiny-voca not found at {tts} — rendering silent')
    else:
        for k, sc in enumerate(scenes):
            w = adir / f's{k:02d}.wav'
            r = subprocess.run([sys.executable, str(tts), '--text', sc.get('speak', ''),
                                '--voice', sc.get('voice', 'M2'), '--output', str(w)],
                               capture_output=True, timeout=300)
            if w.exists() and w.stat().st_size > 1000:
                wavs.append(w)
            else:
                print(f'  line {k} produced no audio: {r.stderr.decode()[:120]}')
        print(f'  audio: {len(wavs)}/{len(scenes)} lines synthesised')
        if len(wavs) != len(scenes):
            print('  WARNING: partial audio — the film will not match the script')

    concat = wd / 'a.txt'
    if wavs:
        concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in wavs), encoding='utf-8')
        aj = wd / 'a.wav'
        subprocess.run([str(ff / 'ffmpeg'), '-y', '-v', 'error', '-f', 'concat', '-safe', '0',
                        '-i', str(concat), str(aj)], check=True, timeout=600)
        # pad audio to the picture length — never let audio cut the film
        probe = subprocess.run([str(ff / 'ffprobe'), '-v', 'error', '-show_entries',
                                'format=duration', '-of', 'json', str(aj)],
                               capture_output=True, text=True, timeout=120)
        adur = float(json.loads(probe.stdout)['format']['duration'])
        want = nf / a.fps
        cmd = [str(ff / 'ffmpeg'), '-y', '-v', 'error']
        # PICTURE MUST COVER THE AUDIO.
        # The old code set -t max(want, adur) while feeding only `nf` frames.
        # When the speech ran longer than the picture, ffmpeg held the last
        # frame for the remainder and the film reported ok:true — a frozen
        # tail of 15.8 s, 23.6 s and 38.3 s shipped in three published films.
        # The gait is cyclic, so looping the rendered sequence is honest: it
        # is the same walk continuing, not invented motion.
        loops = 1
        if adur > want + 1e-3:
            loops = int(math.ceil(adur / want))
            cmd += ['-stream_loop', str(loops - 1)]
            print(f'  picture: {want:.2f}s of frames vs {adur:.2f}s of speech '
                  f'-> looping x{loops} to cover it')
        cmd += ['-framerate', str(a.fps), '-i', str(fd / 'f%05d.png'), '-i', str(aj)]
        if adur < want:
            cmd += ['-filter_complex', f'apad=whole_dur={want}']
        cmd += ['-c:v', 'h264_nvenc', '-preset', 'p5', '-b:v', '6M', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '160k', '-t', f'{max(want, adur):.3f}', str(out)]
        subprocess.run(cmd, check=True, timeout=1800)
        # VERIFY THE MUX, do not assume it. A gate that only reads pixels
        # cannot see a frozen tail: every frame it samples is a real frame.
        pr = subprocess.run([str(ff / 'ffprobe'), '-v', 'error', '-show_entries',
                             'stream=codec_type,duration', '-of', 'json', str(out)],
                            capture_output=True, text=True, timeout=120)
        st = {s['codec_type']: float(s['duration'])
              for s in json.loads(pr.stdout)['streams'] if s.get('duration')}
        vd, ad = st.get('video', 0.0), st.get('audio', 0.0)
        if abs(vd - ad) > 0.15:
            raise RuntimeError(
                f'DURATION MISMATCH: video {vd:.3f}s vs audio {ad:.3f}s '
                f'({abs(vd-ad):.2f}s of frozen picture). Refusing to report ok.')
        print(f'  mux verified: video {vd:.3f}s == audio {ad:.3f}s')
    else:
        subprocess.run([str(ff / 'ffmpeg'), '-y', '-v', 'error', '-framerate', str(a.fps),
                        '-i', str(fd / 'f%05d.png'), '-c:v', 'h264_nvenc', '-preset', 'p5',
                        '-b:v', '6M', '-pix_fmt', 'yuv420p', '-t', f'{nf / a.fps:.3f}',
                        str(out)], check=True, timeout=1800)

    meta = {'ok': True, 'out': str(out), 'frames': nf, 'seconds': round(nf / a.fps, 3),
            'size': [W, H], 'panels': NB + 1, 'panel_viewport': [VW, VH],
            'layout': f'{COLS}x{ROWS}', 'bodies': NB,
            'triangles': len(v0) * NB, 'raster_ms': round(rms / nf, 1),
            'cast': IDS, 'texture': a.texture, 'void': list(VOID),
            'raster_bg': list(RASTER_BG), 'grants': False}
    (wd / 'render.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
