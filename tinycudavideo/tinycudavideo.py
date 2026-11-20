#!/usr/bin/env python3
"""tinyCUDAVIDEO — GPU frames to a receipted film, or a refusal.

The missing member of the tiny family. tinycuda grades pixels, tinymujoco grades
motion, tinycan grades the bus. None of them made a FILM. Every film so far was
a bespoke script in agents/, and the same defect shipped three times because
each script muxed its own way.

THE LESSON THIS MODULE EXISTS TO ENFORCE
A pixel gate cannot see a frozen tail. Every frame it samples is a real frame;
the defect is that the picture STOPPED while the audio continued. Three
published films carried 15.82 s, 23.55 s and 38.34 s of frozen picture and every
one of them returned PASS. So `gate()` here checks the MUX as well as the
pixels, and `produce()` refuses rather than returning a receipt for a broken
film. Thresholds are never lowered to pass; fix the scene.

    from tinycudavideo import produce
    r = produce(frames, out='film.mp4', fps=24, audio='voice.wav')
    # r['ok'] is True only if pixels AND mux AND coverage all pass

    python tinycudavideo.py doctor
    python tinycudavideo.py gate film.mp4
    python tinycudavideo.py receipt film.mp4
    python tinycudavideo.py grade a.mp4 b.mp4

Deterministic: same frames + same encoder settings -> same bytes -> same hash.
Zero tokens. No model is consulted at any point.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

# --- gate thresholds. Never lowered to make a film pass. ---------------------
LUM_MIN = 20.0
CON_MIN = 10.0
MOV_MIN = 0.5
BLACK_MAX_PCT = 5.0
MUX_TOLERANCE_S = 0.15


def _ffmpeg() -> Path:
    """NVENC-capable ffmpeg. Driver 592.27 exposes API 13.0; ffmpeg 9 wants 13.1
    and fails. 7.1 targets 13.0 and works. Prefer the pinned build."""
    env = os.environ.get('TINYCUDAVIDEO_FFMPEG')
    if env and Path(env).exists():
        return Path(env)
    home = os.environ.get('HERMES_HOME') or os.environ.get('LOCALAPPDATA', '')
    pinned = Path(home) / 'tools' / 'ffmpeg-7.1-nvenc' / 'bin'
    if (pinned / 'ffmpeg.exe').exists():
        return pinned
    if (pinned / 'ffmpeg').exists():
        return pinned
    w = shutil.which('ffmpeg')
    if w:
        return Path(w).parent
    raise FileNotFoundError('no ffmpeg found; set TINYCUDAVIDEO_FFMPEG')


def doctor() -> dict:
    d = {'module': 'tinycudavideo', 'python': sys.version.split()[0]}
    try:
        import cupy as cp
        d['cupy'] = cp.__version__
        d['cuda_devices'] = cp.cuda.runtime.getDeviceCount()
        p = cp.cuda.runtime.getDeviceProperties(0)
        d['gpu'] = p['name'].decode() if isinstance(p['name'], bytes) else str(p['name'])
        d['vram_mib'] = int(p['totalGlobalMem'] / 2**20)
    except Exception as exc:
        d['cupy'] = None
        d['cupy_error'] = f'{type(exc).__name__}: {exc}'
    try:
        ff = _ffmpeg()
        d['ffmpeg_dir'] = str(ff)
        exe = ff / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        r = subprocess.run([str(exe), '-hide_banner', '-encoders'],
                           capture_output=True, timeout=120)
        txt = r.stdout.decode('utf-8', 'replace')
        d['nvenc'] = 'h264_nvenc' in txt
        d['hevc_nvenc'] = 'hevc_nvenc' in txt
    except Exception as exc:
        d['ffmpeg_dir'] = None
        d['ffmpeg_error'] = f'{type(exc).__name__}: {exc}'
        d['nvenc'] = False
    try:
        import numpy, PIL
        d['numpy'] = numpy.__version__
        d['pillow'] = PIL.__version__
    except Exception as exc:
        d['imaging_error'] = str(exc)
    d['ok'] = bool(d.get('nvenc')) and d.get('cupy') is not None
    d['gate'] = {'lum_min': LUM_MIN, 'con_min': CON_MIN, 'mov_min': MOV_MIN,
                 'black_max_pct': BLACK_MAX_PCT, 'mux_tolerance_s': MUX_TOLERANCE_S}
    return d


def _probe(path: Path) -> dict:
    ff = _ffmpeg()
    exe = ff / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
    r = subprocess.run([str(exe), '-v', 'error', '-show_entries',
                        'stream=codec_type,codec_name,width,height,duration,nb_frames',
                        '-of', 'json', str(path)], capture_output=True, text=True, timeout=180)
    streams = json.loads(r.stdout).get('streams', [])
    out = {'streams': streams}
    for s in streams:
        if s.get('codec_type') == 'video':
            out['video'] = s
        elif s.get('codec_type') == 'audio':
            out['audio'] = s
    return out


def gate(path: Path, sample: int = 48, scale=None) -> dict:
    """Pixels AND mux. A film passes only if both do.

    The pixel half is the SupervisorVideo contract, measured at NATIVE
    resolution by default. The thresholds (lum 20, con 10, mov 0.5) were
    calibrated by that instrument at full resolution; measuring at 180x320 and
    applying them anyway is a mis-calibration, not a stricter gate. Downscaling
    averages away exactly the fine detail that carries motion in a HUD-heavy
    film: tinycan-916 measures mov 1.298 native and 0.435 at 180x320.

    Pass scale=(w,h) for a fast approximation, and the result records the scale
    so nobody compares it against a native measurement.

    The mux half is what was missing everywhere: video and audio must cover the
    same span, or the picture froze while the voice continued.
    """
    import numpy as np
    from PIL import Image
    path = Path(path)
    if not path.exists():
        return {'ok': False, 'reason': f'not found: {path}'}
    pr = _probe(path)
    v = pr.get('video')
    if not v:
        return {'ok': False, 'reason': 'no video stream'}
    nb = int(v.get('nb_frames') or 0)
    vd = float(v.get('duration') or 0)
    a = pr.get('audio')
    ad = float(a['duration']) if a and a.get('duration') else None

    ff = _ffmpeg()
    exe = ff / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        cmd = [str(exe), '-v', 'error', '-i', str(path)]
        if scale:
            cmd += ['-vf', f'scale={scale[0]}:{scale[1]}']
        cmd += ['-frames:v', str(max(nb, 1)), str(td / 's%05d.png')]
        subprocess.run(cmd, check=True, timeout=900)
        fs = sorted(td.glob('s*.png'))
        if not fs:
            return {'ok': False, 'reason': 'no frames decoded'}
        step = max(1, len(fs) // sample)
        picked = fs[::step]
        arrs = [np.asarray(Image.open(p).convert('RGB'), np.float32) for p in picked]
        lum = float(np.mean([x.mean() for x in arrs]))
        con = float(np.mean([x.std() for x in arrs]))
        mov = 0.0
        for i in range(1, len(arrs)):
            mov += float(np.abs(arrs[i] - arrs[i - 1]).mean())
        mov = mov / max(1, len(arrs) - 1)
        black = 100.0 * sum(1 for x in arrs if x.mean() < 4.0) / len(arrs)
        measured_scale = [int(arrs[0].shape[1]), int(arrs[0].shape[0])]

    checks = {
        'luminance': lum > LUM_MIN,
        'contrast': con > CON_MIN,
        'motion': mov > MOV_MIN,
        'black_frames': black < BLACK_MAX_PCT,
    }
    mux_delta = None
    if ad is not None:
        mux_delta = abs(vd - ad)
        checks['mux_match'] = mux_delta <= MUX_TOLERANCE_S
    # a frozen tail also shows as picture shorter than the container
    ok = all(checks.values())
    reasons = [k for k, v_ in checks.items() if not v_]
    return {
        'ok': ok,
        'pixels': {'luminance': round(lum, 2), 'contrast': round(con, 2),
                   'motion': round(mov, 3), 'black_pct': round(black, 2),
                   'analysis_scale': measured_scale, 'sampled': len(picked)},
        'mux': {'video_s': round(vd, 3),
                'audio_s': round(ad, 3) if ad is not None else None,
                'delta_s': round(mux_delta, 3) if mux_delta is not None else None,
                'frozen_tail_s': round(max(0.0, (ad or 0) - vd), 3)},
        'size': [int(v.get('width', 0)), int(v.get('height', 0))],
        'frames': nb,
        'checks': checks,
        'failed': reasons,
        'note': 'motion is measured at analysis_scale. Native by default, matching '
                'the instrument the thresholds came from. A downscaled measurement '
                'is a different instrument — never compare the two silently.',
    }


def produce(frames, out, fps: int = 24, audio=None, bitrate: str = '6M') -> dict:
    """frames: iterable of HxWx3 uint8 arrays, or a directory of PNGs.

    Loops the picture to cover longer audio (a cyclic gait continuing is honest;
    a frozen frame is not), then GATES. Returns ok=False with the reason rather
    than a receipt for a broken film.
    """
    import math
    import numpy as np
    from PIL import Image
    out = Path(out)
    wd = out.parent / (out.stem + '-tcv')
    fd = wd / 'frames'
    fd.mkdir(parents=True, exist_ok=True)
    if isinstance(frames, (str, Path)) and Path(frames).is_dir():
        src = sorted(Path(frames).glob('*.png'))
        nf = len(src)
        for i, p in enumerate(src):
            shutil.copy2(p, fd / f'f{i:05d}.png')
    else:
        nf = 0
        for i, fr in enumerate(frames):
            Image.fromarray(np.asarray(fr, np.uint8)).save(fd / f'f{i:05d}.png')
            nf = i + 1
    if nf == 0:
        return {'ok': False, 'reason': 'no frames supplied'}

    ff = _ffmpeg()
    exe = ff / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
    want = nf / fps
    loops, adur = 1, None
    if audio:
        audio = Path(audio)
        p = subprocess.run([str(ff / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')),
                            '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'json', str(audio)], capture_output=True, text=True, timeout=180)
        adur = float(json.loads(p.stdout)['format']['duration'])
        if adur > want + 1e-3:
            loops = int(math.ceil(adur / want))
    cmd = [str(exe), '-y', '-v', 'error']
    if loops > 1:
        cmd += ['-stream_loop', str(loops - 1)]
    cmd += ['-framerate', str(fps), '-i', str(fd / 'f%05d.png')]
    if audio:
        cmd += ['-i', str(audio)]
        if adur < want:
            cmd += ['-filter_complex', f'apad=whole_dur={want}']
    cmd += ['-c:v', 'h264_nvenc', '-preset', 'p5', '-b:v', bitrate, '-pix_fmt', 'yuv420p']
    if audio:
        cmd += ['-c:a', 'aac', '-b:a', '160k', '-t', f'{max(want, adur):.3f}']
    else:
        cmd += ['-t', f'{want:.3f}']
    cmd += ['-movflags', '+faststart', str(out)]
    subprocess.run(cmd, check=True, timeout=3600)

    g = gate(out)
    res = {'ok': g['ok'], 'out': str(out), 'frames_rendered': nf, 'picture_loops': loops,
           'fps': fps, 'gate': g,
           'sha256': hashlib.sha256(out.read_bytes()).hexdigest()}
    if not g['ok']:
        res['reason'] = 'gate failed: ' + ', '.join(g['failed'])
        res['refused'] = True
    (wd / 'produce.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    return res


def receipt(path: Path) -> dict:
    path = Path(path)
    g = gate(path)
    return {'file': path.name, 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'gate': g, 'ok': g['ok'],
            'citation': f'æ://film/{path.stem}',
            'note': 'the DOI is the hash of the delivered bytes, not of the source'}


def grade(a: Path, b: Path) -> dict:
    ha = hashlib.sha256(Path(a).read_bytes()).hexdigest()
    hb = hashlib.sha256(Path(b).read_bytes()).hexdigest()
    return {'reward': 1.0 if ha == hb else 0.0, 'tokens_used': 0,
            'method': 'byte_compare', 'a': ha[:16], 'b': hb[:16],
            'note': 'encoder settings are part of the contract; a different preset '
                    'is a different film even from identical frames'}


def main() -> int:
    ap = argparse.ArgumentParser(description='tinyCUDAVIDEO — GPU frames to a receipted film')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor')
    for n in ('gate', 'receipt'):
        p = sub.add_parser(n); p.add_argument('film')
    g = sub.add_parser('grade'); g.add_argument('a'); g.add_argument('b')
    p = sub.add_parser('produce')
    p.add_argument('--frames', required=True); p.add_argument('--out', required=True)
    p.add_argument('--fps', type=int, default=24); p.add_argument('--audio')
    a = ap.parse_args()
    if a.cmd == 'doctor':
        d = doctor(); print(json.dumps(d, indent=2)); return 0 if d['ok'] else 1
    if a.cmd == 'gate':
        r = gate(Path(a.film)); print(json.dumps(r, indent=2)); return 0 if r['ok'] else 1
    if a.cmd == 'receipt':
        r = receipt(Path(a.film)); print(json.dumps(r, indent=2)); return 0 if r['ok'] else 1
    if a.cmd == 'grade':
        r = grade(Path(a.a), Path(a.b)); print(json.dumps(r, indent=2)); return 0 if r['reward'] == 1.0 else 1
    if a.cmd == 'produce':
        r = produce(Path(a.frames), Path(a.out), a.fps, a.audio)
        print(json.dumps(r, indent=2)); return 0 if r['ok'] else 1
    return 2


if __name__ == '__main__':
    sys.exit(main())
