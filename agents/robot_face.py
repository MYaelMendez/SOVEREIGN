"""robot_face — a real face tablet, not three rectangles.

Drawn at the projected head position. Supersampled 3x then downscaled so the
curves are smooth at 720p. Carries: bezel + screen glow, capsule eyes with
iris/pupil/highlight, eased eyelids, a viseme mouth set, brows that carry the
state, a charge arc, scanlines and a pixel grid.

Visemes (0-7): rest, M/B/P closed, A open, E wide, I narrow, O round, U small, F/V
"""
from PIL import Image, ImageDraw, ImageFilter

SS = 3  # supersample factor


def _rr(dr, box, r, fill=None, outline=None, width=1):
    dr.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def _mix(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


# mouth geometry per viseme: (width_factor, height_factor, roundness)
VISEMES = [
    (0.52, 0.06, 0.5),   # 0 rest
    (0.46, 0.02, 0.5),   # 1 M/B/P closed
    (0.40, 0.42, 0.9),   # 2 A open
    (0.62, 0.20, 0.4),   # 3 E wide
    (0.56, 0.09, 0.3),   # 4 I narrow
    (0.30, 0.34, 1.0),   # 5 O round
    (0.22, 0.22, 1.0),   # 6 U small
    (0.50, 0.10, 0.3),   # 7 F/V
]


def face(size, rgb, *, viseme=0, blink=0.0, gaze=(0.0, 0.0), charge=None,
         state='IDLE', brow=0.0, glow=1.0, scan=True):
    """Return an RGBA face tablet image of `size` (w,h) at 1x scale.

    blink 0=open 1=closed · gaze (-1..1, -1..1) · charge 0..1 or None
    brow -1 furrowed .. +1 raised
    """
    w, h = size[0] * SS, size[1] * SS
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(2 * SS)
    bezel = [pad, pad, w - pad, h - pad]
    rad = int(10 * SS)

    # bezel + inner screen
    _rr(d, bezel, rad, fill=(16, 17, 20, 242), outline=rgb + (255,), width=max(1, int(1.6 * SS)))
    inset = int(4 * SS)
    scr = [bezel[0] + inset, bezel[1] + inset, bezel[2] - inset, bezel[3] - inset]
    _rr(d, scr, int(7 * SS), fill=(6, 8, 10, 255))

    # screen glow
    gl = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    _rr(gd, scr, int(7 * SS), fill=rgb + (int(26 * glow),))
    gl = gl.filter(ImageFilter.GaussianBlur(6 * SS))
    img = Image.alpha_composite(img, gl)
    d = ImageDraw.Draw(img)

    # pixel grid
    if scan:
        step = max(2, int(3 * SS))
        for yy in range(scr[1], scr[3], step):
            d.line([(scr[0], yy), (scr[2], yy)], fill=rgb + (10,), width=1)

    cx, cy = w // 2, h // 2
    eye_y = cy - int(7 * SS)
    eye_dx = int(15 * SS)
    ew, eh = int(15 * SS), int(9 * SS)

    # brows carry the state
    for sx in (-1, 1):
        bx = cx + sx * eye_dx
        by = eye_y - int(11 * SS) - int(brow * 2 * SS)
        tilt = int(brow * 2.2 * SS) * (-sx if state == 'REFUSED' else sx)
        d.line([(bx - ew // 2, by + tilt), (bx + ew // 2, by - tilt)],
               fill=rgb + (150 if state != 'IDLE' else 70,), width=max(1, int(1.4 * SS)))

    # eyes: capsule + iris + pupil + highlight, with eased lid
    open_h = max(int(1.2 * SS), int(eh * (1.0 - 0.94 * blink)))
    for sx in (-1, 1):
        ex = cx + sx * eye_dx
        box = [ex - ew // 2, eye_y - open_h // 2, ex + ew // 2, eye_y + open_h // 2]
        _rr(d, box, open_h // 2, fill=rgb + (235,))
        if blink < 0.55:
            gx = ex + int(gaze[0] * 3.2 * SS)
            gy = eye_y + int(gaze[1] * 1.8 * SS)
            pr = max(1, int(2.6 * SS * (1 - blink)))
            d.ellipse([gx - pr, gy - pr, gx + pr, gy + pr], fill=(8, 10, 12, 230))
            hr = max(1, int(0.9 * SS))
            d.ellipse([gx - pr // 2 - hr, gy - pr // 2 - hr,
                       gx - pr // 2 + hr, gy - pr // 2 + hr], fill=(255, 255, 255, 200))

    # mouth: viseme shape
    wf, hf, rnd = VISEMES[max(0, min(7, int(viseme)))]
    mw = int(30 * SS * wf)
    mh = max(int(1.4 * SS), int(22 * SS * hf))
    my = cy + int(13 * SS)
    mbox = [cx - mw // 2, my - mh // 2, cx + mw // 2, my + mh // 2]
    _rr(d, mbox, int(mh / 2 * rnd), fill=rgb + (225,))
    if hf > 0.18:  # inner mouth shadow when open
        ib = [mbox[0] + int(2 * SS), mbox[1] + int(2 * SS),
              mbox[2] - int(2 * SS), mbox[3] - int(2 * SS)]
        if ib[2] > ib[0] and ib[3] > ib[1]:
            _rr(d, ib, int(mh / 3 * rnd), fill=(6, 8, 10, 190))

    # charge arc along the bottom of the screen
    if charge is not None:
        c = max(0.0, min(1.0, charge))
        bx0, bx1 = scr[0] + int(8 * SS), scr[2] - int(8 * SS)
        by = scr[3] - int(5 * SS)
        d.line([(bx0, by), (bx1, by)], fill=rgb + (48,), width=max(1, int(2 * SS)))
        d.line([(bx0, by), (bx0 + int((bx1 - bx0) * c), by)],
               fill=rgb + (215,), width=max(1, int(2 * SS)))

    # corner status dot
    dr = int(1.8 * SS)
    dx, dy = scr[2] - int(6 * SS), scr[1] + int(6 * SS)
    d.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=rgb + (200,))

    return img.resize((size[0], size[1]), Image.LANCZOS)


def paste_face(base, centre, size, rgb, **kw):
    """Composite a face onto an RGB base at pixel centre."""
    f = face(size, rgb, **kw)
    x = int(centre[0] - size[0] / 2)
    y = int(centre[1] - size[1] / 2)
    base.paste(f, (x, y), f)
    return base
