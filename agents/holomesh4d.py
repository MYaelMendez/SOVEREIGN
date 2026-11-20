#!/usr/bin/env python3
"""holomesh4d — the MÆCH 4D HoloMesh, on tinycuda instead of a 2D canvas.

WHAT WAS WRONG
mech-4d-holomesh.html is 877 lines of hand-written JavaScript drawing dots on a
Canvas2D context. The 4D math is genuine — verified by driving project4Dto2D
across five time slices, 375/375 nodes moved, max displacement 227.20 px — but
it is CPU raster, no depth buffer, no occlusion, no lighting, and no receipt.
It also carries the MÆCH name without touching the Mech runtime.

WHAT THIS DOES
Same 375 nodes and 1150 edges, extracted from the live page. Same four-plane
rotation and stereographic projection, ported exactly. Rendered as real 3D
geometry through tinycuda's CuPy rasteriser: octahedral nodes, edge struts,
depth-correct occlusion, per-face shading, deterministic bytes, gradeable.

    python holomesh4d.py render --out film.mp4
    python holomesh4d.py probe          # the projection, measured
    python holomesh4d.py grade a.png b.png

The node set is data, not code: holomesh-nodes.json holds the coordinates the
browser produced, so this renders THE mesh, not a lookalike.
"""
from __future__ import annotations
import argparse, json, math, os, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, r'C:\æ\tinycuda')

TYPE_COL = {
    'compute': (0.831, 0.686, 0.216),   # gold
    'network': (0.176, 0.831, 0.749),   # teal
    'sensor':  (0.549, 0.447, 1.000),   # violet
    'storage': (1.000, 0.251, 0.863),   # magenta
}


def octahedron(c, r):
    """6 vertices, 8 faces — cheap, reads as a node at any zoom."""
    x, y, z = c
    V = np.array([[x+r,y,z],[x-r,y,z],[x,y+r,z],[x,y-r,z],[x,y,z+r],[x,y,z-r]], np.float32)
    F = [(0,2,4),(2,1,4),(1,3,4),(3,0,4),(2,0,5),(1,2,5),(3,1,5),(0,3,5)]
    return np.array([[V[a],V[b],V[c_]] for a,b,c_ in F], np.float32)


def strut(a, b, t):
    """A thin box between two points — an edge with actual thickness."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    d = b - a
    L = np.linalg.norm(d)
    if L < 1e-6:
        return np.zeros((0,3,3), np.float32)
    d = d / L
    up = np.array([0,0,1], np.float32) if abs(d[2]) < 0.9 else np.array([1,0,0], np.float32)
    u = np.cross(d, up); u /= (np.linalg.norm(u) + 1e-12)
    v = np.cross(d, u)
    o = np.stack([u*t, v*t], 0)
    corners = []
    for p in (a, b):
        for su, sv in ((1,1),(-1,1),(-1,-1),(1,-1)):
            corners.append(p + su*o[0] + sv*o[1])
    A, B = np.array(corners[:4]), np.array(corners[4:])
    tris = []
    for i in range(4):
        j = (i+1) % 4
        tris += [[A[i],A[j],B[j]], [A[i],B[j],B[i]]]
    return np.array(tris, np.float32)


def project4(nodes, rot, time_slice):
    """Exact port of project4Dto2D: XY, ZW, XZ rotations then stereographic.

    Returns 3D positions (x, y, depth) plus a proximity weight. The browser
    collapses to 2D immediately; we keep depth so the GPU can occlude.
    """
    P = np.array([[n['x'], n['y'], n['z'], n['w'] - time_slice] for n in nodes], np.float64)
    x1, y1, z1, w1 = P[:,0], P[:,1], P[:,2], P[:,3]
    cx, sx = math.cos(rot['x']), math.sin(rot['x'])
    x2, y2 = x1*cx - y1*sx, x1*sx + y1*cx
    cz, sz = math.cos(rot['z']), math.sin(rot['z'])
    z2, w2 = z1*cz - w1*sz, z1*sz + w1*cz
    cy, sy = math.cos(rot['y']), math.sin(rot['y'])
    x3, z3 = x2*cy - z2*sy, x2*sy + z2*cy
    cw, sw = math.cos(rot.get('w',0.0)), math.sin(rot.get('w',0.0))
    x4, w4 = x3*cw - w2*sw, x3*sw + w2*cw
    # stereographic 4D -> 3D from the w pole
    denom = np.maximum(1.0, 600.0 - w4)
    k = 600.0 / denom
    out = np.stack([x4*k, y2*k, z3*k], 1) / 250.0
    prox = np.maximum(0.0, 1.0 - np.abs(P[:,3]) / 200.0)
    return out.astype(np.float32), prox.astype(np.float32)


def build(nodes, edges, rot, ts, node_r=0.055, edge_t=0.008):
    pos, prox = project4(nodes, rot, ts)
    idx = {n['id']: i for i, n in enumerate(nodes)}
    Vs, Cs = [], []
    for i, n in enumerate(nodes):
        base = np.array(TYPE_COL.get(n['type'], (0.7,0.7,0.7)), np.float32)
        # temporal proximity dims the node, never below a visible floor
        w = 0.34 + 0.66 * prox[i]
        g = octahedron(pos[i], node_r * (0.7 + 0.6*prox[i]))
        Vs.append(g); Cs.append(np.tile(base*w, (len(g),1)))
    for a, b in edges:
        ia, ib = idx.get(a), idx.get(b)
        if ia is None or ib is None:
            continue
        s = strut(pos[ia], pos[ib], edge_t)
        if not len(s):
            continue
        w = 0.22 + 0.5 * min(prox[ia], prox[ib])
        Vs.append(s); Cs.append(np.tile(np.array([0.42,0.38,0.22],np.float32)*w, (len(s),1)))
    V = np.concatenate(Vs)
    C = np.concatenate(Cs).astype(np.float32)
    e1, e2 = V[:,1]-V[:,0], V[:,2]-V[:,0]
    N = np.cross(e1, e2)
    N /= (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)
    return V, N.astype(np.float32), C, pos, prox


def load():
    S = Path(os.environ['HERMES_HOME']) / 'cache' / 'scratch'
    d = json.loads((S / 'holomesh-nodes.json').read_text(encoding='utf-8'))
    return d['nodes'], d['edges']


def probe():
    nodes, edges = load()
    rot = {'x':0.005,'y':0.007,'z':0.003,'w':0.002}
    rows = []
    for ts in (0, 50, 100, 150, 200):
        p, pr = project4(nodes, rot, ts)
        rows.append({'t': ts, 'node0': [round(float(v),4) for v in p[0]],
                     'proximity_mean': round(float(pr.mean()),4)})
    p0,_ = project4(nodes, rot, 0); p1,_ = project4(nodes, rot, 150)
    d = np.linalg.norm(p1-p0, axis=1)
    return {'nodes': len(nodes), 'edges': len(edges), 'slices': rows,
            'moved': int((d > 0.002).sum()), 'max_displacement': round(float(d.max()),4),
            'source': 'holomesh-nodes.json extracted from the live page'}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('probe')
    r = sub.add_parser('render')
    r.add_argument('--out', required=True); r.add_argument('--seconds', type=float, default=10.0)
    r.add_argument('--fps', type=int, default=24)
    g = sub.add_parser('grade'); g.add_argument('a'); g.add_argument('b')
    a = ap.parse_args()

    if a.cmd == 'probe':
        print(json.dumps(probe(), indent=2)); return 0
    if a.cmd == 'grade':
        import hashlib
        ha = hashlib.sha256(Path(a.a).read_bytes()).hexdigest()
        hb = hashlib.sha256(Path(a.b).read_bytes()).hexdigest()
        print(json.dumps({'reward': 1.0 if ha==hb else 0.0, 'tokens_used': 0,
                          'a': ha[:16], 'b': hb[:16]}, indent=2))
        return 0 if ha==hb else 1

    import tinycuda as TC
    from PIL import Image, ImageDraw, ImageFont
    nodes, edges = load()
    W, H = 720, 1280
    VH = 900
    ras = TC.Raster(W, VH)
    P = TC.persp(42.0, 0.05, 200.0, aspect=W/VH)
    nf = int(round(a.seconds*a.fps))
    out = Path(a.out); wd = out.parent/(out.stem+'-hm'); fd = wd/'frames'
    fd.mkdir(parents=True, exist_ok=True)

    def font(sz, b=False):
        try:
            return ImageFont.truetype('C:/Windows/Fonts/consolab.ttf' if b
                                      else 'C:/Windows/Fonts/consola.ttf', sz)
        except Exception:
            return ImageFont.load_default()
    F_T, F_M, F_S, F_X = font(26,True), font(20,True), font(15), font(12)
    G8=(212,175,55); INK=(232,230,223); DIM=(138,122,63); TEAL=(45,212,191)

    print(f'  {len(nodes)} nodes · {len(edges)} edges · rendering {nf} frames…')
    t0=time.time(); rms=0.0; tri0=0
    for i in range(nf):
        u = i/max(1,nf-1)
        ts = 200.0*u
        rot = {'x':0.005+0.9*u, 'y':0.007+1.3*u, 'z':0.003+0.6*u, 'w':0.002+0.4*u}
        V,N,C,pos,prox = build(nodes, edges, rot, ts)
        tri0 = len(V)
        ctr = np.array([0,0,0], np.float32)
        VIEW = P @ TC.look_at(ctr+[4.6,-0.5,1.4], ctr)
        tsx=time.time()
        px = ras.render(V,N,C,VIEW)
        rms += (time.time()-tsx)*1000
        img = Image.new('RGB',(W,H),(10,11,15))
        img.paste(Image.fromarray(px),(0,72))
        d = ImageDraw.Draw(img)
        d.rectangle([0,0,W,66], fill=G8)
        d.text((20,8),'4D HOLOMESH · tinyCUDA',font=F_T,fill=(5,5,5))
        d.text((20,42),'375 nodes · 1150 edges · GPU raster · stereographic',font=F_X,fill=(58,48,16))
        y = VH+84
        d.text((20,y),f't = {ts:.0f}',font=F_M,fill=G8); y+=28
        d.text((20,y),f'{tri0:,} triangles · {rms/(i+1):.0f} ms/frame',font=F_S,fill=INK); y+=24
        d.text((20,y),f'proximity mean {prox.mean():.3f} · nearest {prox.max():.3f}',font=F_S,fill=DIM); y+=30
        for k,(t_,col) in enumerate(TYPE_COL.items()):
            n_ = sum(1 for n in nodes if n['type']==t_)
            c8 = tuple(int(v*255) for v in col)
            d.rectangle([20+k*172,y,20+k*172+12,y+12], fill=c8)
            d.text((38+k*172,y-2),f'{t_} {n_}',font=F_X,fill=INK)
        d.rectangle([0,H-72,W,H],fill=(8,9,12))
        d.text((20,H-62),'was: Canvas2D dots, no depth, no receipt',font=F_X,fill=DIM)
        d.text((20,H-42),'now: CuPy depth buffer · occlusion · shading · SHA-256',font=F_X,fill=TEAL)
        d.text((20,H-22),'>_æ://  ·  tinycuda grade · zero tokens',font=F_X,fill=G8)
        img.save(fd/f'f{i:05d}.png')
        if i%48==0: print(f'    {i}/{nf} · {tri0:,} tris · {rms/(i+1):.0f} ms')
    meta={'frames':nf,'seconds':a.seconds,'fps':a.fps,'size':[W,H],
          'nodes':len(nodes),'edges':len(edges),'triangles':tri0,
          'raster_ms':round(rms/nf,1),'wall_s':round(time.time()-t0,1),
          'source':'mech-4d-holomesh.html node set, extracted live'}
    (wd/'render.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(f'  {nf} frames · {tri0:,} tris · {rms/nf:.0f} ms/frame · {time.time()-t0:.0f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
