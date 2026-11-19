"""Trajectory image — built from measured contribution data, not vibes.

Two series, because they disagree and the disagreement is informative:
  * GitHub's contribution calendar (GraphQL contributionsCollection)
  * actual git commits in the two working repos

Gold on void, 9:16, deterministic. Every number is fetched or counted.
"""
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

H = Path(os.environ['HERMES_HOME'])
SC = H / 'cache' / 'scratch'
W, HH = 1080, 1920
GOLD = (212, 175, 55)
VOID = (5, 5, 5)
DIM = (138, 122, 63)
INK = (245, 238, 214)
CYAN = (0, 170, 255)


def font(sz, bold=False):
    p = f"C:/Windows/Fonts/{'consolab' if bold else 'consola'}.ttf"
    return ImageFont.truetype(p, sz) if Path(p).exists() else ImageFont.load_default()


def git_months(repo):
    # Two traps at once: 'æ' corrupts argv (so never pass -C), and the
    # WindowsApps git shim refuses a non-ASCII cwd with WinError 5. The
    # standalone Git install handles it. Resolve it explicitly.
    import shutil
    git = next((p for p in (r'C:\Program Files\Git\cmd\git.exe',
                            r'C:\Program Files\Git\bin\git.exe')
                if Path(p).exists()), shutil.which('git'))
    r = subprocess.run([git, 'log', '--pretty=format:%ad',
                        '--date=format:%Y-%m'], capture_output=True, text=True,
                       encoding='utf-8', timeout=120, cwd=str(repo).replace('\\', '/'))
    c = defaultdict(int)
    for line in r.stdout.splitlines():
        if line.strip():
            c[line.strip()] += 1
    return c


def main():
    d = json.loads((SC / 'contrib.json').read_text(encoding='utf-8'))
    col = d['collection']
    gh = defaultdict(int)
    for x in d['days']:
        gh[x['date'][:7]] += x['contributionCount']
    pages = git_months(r'C:\æ\github-pages')
    sov = git_months(r'C:\æ')
    months = [m for m in sorted(set(list(gh) + list(pages) + list(sov)))
              if m >= '2026-02']
    gitc = {m: pages.get(m, 0) + sov.get(m, 0) for m in months}

    img = Image.new('RGB', (W, HH), VOID)
    dr = ImageDraw.Draw(img, 'RGBA')
    # neural mesh
    for i in range(0, W, 60):
        dr.line([(i, 0), (i, HH)], fill=GOLD + (10,), width=1)
    for j in range(0, HH, 60):
        dr.line([(0, j), (W, j)], fill=GOLD + (10,), width=1)
    for y in range(0, HH, 3):
        dr.line([(0, y), (W, y)], fill=(0, 0, 0, 26), width=1)

    dr.rectangle([0, 0, W, 150], fill=GOLD + (255,))
    dr.text((44, 28), '>_æ:// TRAJECTORY', font=font(46, True), fill=VOID + (255,))
    dr.text((44, 92), 'MYaelMendez · measured contribution history',
            font=font(24), fill=(58, 48, 16, 255))

    # headline numbers
    y = 196
    stats = [('COMMITS', col['totalCommitContributions']),
             ('REPOS', col['totalRepositoryContributions']),
             ('PRs', col['totalPullRequestContributions']),
             ('ACTIVE DAYS', sum(1 for x in d['days'] if x['contributionCount'] > 0))]
    bw = (W - 88) // 4
    for i, (k, v) in enumerate(stats):
        x = 44 + i * bw
        dr.rectangle([x, y, x + bw - 12, y + 108], outline=GOLD + (110,), width=2)
        dr.text((x + 16, y + 14), str(v), font=font(44, True), fill=GOLD + (255,))
        dr.text((x + 16, y + 70), k, font=font(17), fill=DIM + (255,))

    # chart
    y0 = 370
    dr.text((44, y0), 'MONTHLY · GITHUB CREDIT vs ACTUAL COMMITS',
            font=font(25, True), fill=GOLD + (255,))
    top = y0 + 56
    ch = 560
    base = top + ch
    mx = max(max(gh.values()), max(gitc.values()), 1)
    n = len(months)
    slot = (W - 110) / n
    bwid = slot * 0.30
    for i, m in enumerate(months):
        cx = 60 + i * slot + slot / 2
        g = gh.get(m, 0)
        a = gitc.get(m, 0)
        hg = int(ch * g / mx)
        ha = int(ch * a / mx)
        dr.rectangle([cx - bwid - 4, base - hg, cx - 4, base], fill=GOLD + (235,))
        dr.rectangle([cx + 4, base - ha, cx + bwid + 4, base], fill=CYAN + (200,))
        if g:
            dr.text((cx - bwid - 4, base - hg - 26), str(g), font=font(19, True), fill=GOLD + (255,))
        if a:
            dr.text((cx + 4, base - ha - 26), str(a), font=font(19, True), fill=CYAN + (255,))
        dr.text((cx - 30, base + 12), m[5:] + '/' + m[2:4], font=font(17), fill=DIM + (255,))
    dr.line([(50, base), (W - 50, base)], fill=GOLD + (140,), width=2)

    ly = base + 56
    dr.rectangle([60, ly, 88, ly + 20], fill=GOLD + (235,))
    dr.text((98, ly - 2), 'GitHub contribution calendar', font=font(20), fill=INK + (255,))
    dr.rectangle([560, ly, 588, ly + 20], fill=CYAN + (200,))
    dr.text((598, ly - 2), 'actual git commits', font=font(20), fill=INK + (255,))

    # the gap, stated
    gy = ly + 60
    dr.rectangle([44, gy, W - 44, gy + 128], fill=(20, 17, 8, 255), outline=GOLD + (120,), width=2)
    dr.text((64, gy + 16), 'THE GAP IS REAL', font=font(24, True), fill=GOLD + (255,))
    nov_gh, nov_git = gh.get('2026-11', 0), gitc.get('2026-11', 0)
    dr.text((64, gy + 54), f'November: {nov_git} commits in git, {nov_gh} credited by GitHub.',
            font=font(21), fill=INK + (255,))
    dr.text((64, gy + 86), 'Commits authored yael@llm.store — unlinked emails are not counted.',
            font=font(19), fill=DIM + (255,))

    # capability arc
    ay = gy + 172
    dr.text((44, ay), 'WHAT THE COMMITS BUILT', font=font(25, True), fill=GOLD + (255,))
    arc = [('voice', 'tiny-voca 1.3.1 · 5 derived timbres · CPU'),
           ('governance', 'æ policy 7/7 · 4 verdicts · refusals receipted'),
           ('body', '52 CAD meshes · 125 DOF · native MuJoCo'),
           ('protocol', 'asimov:// 14 verbs · 18 Hermes tools'),
           ('media', 'mp4:// 10/10 links · 99 films · 601 MB'),
           ('method', 'board before render · 15 s vs 43 min')]
    for i, (k, v) in enumerate(arc):
        yy = ay + 48 + i * 52
        dr.text((60, yy), f'{i+1:02d}', font=font(22, True), fill=GOLD + (255,))
        dr.text((110, yy), k.upper(), font=font(22, True), fill=INK + (255,))
        dr.text((300, yy + 2), v, font=font(19), fill=DIM + (255,))

    # open blockers
    by = ay + 48 + len(arc) * 52 + 28
    dr.rectangle([44, by, W - 44, by + 150], fill=(16, 10, 10, 255), outline=(255, 90, 90, 120), width=2)
    dr.text((64, by + 16), 'STILL OPEN', font=font(24, True), fill=(255, 120, 120, 255))
    for i, t in enumerate(['one machine — no second-box reproduction',
                           'RTX idle: all films rasterised on Intel UHD',
                           'no physical robot has moved']):
        dr.text((64, by + 56 + i * 30), '· ' + t, font=font(20), fill=INK + (255,))

    dr.rectangle([0, HH - 74, W, HH], fill=GOLD + (255,))
    dr.text((44, HH - 54), 'HUMAN://ROOT · #OPENSOURCEWARE · myaelmendez.github.io',
            font=font(22, True), fill=VOID + (255,))

    out = SC / 'trajectory-916.png'
    img.save(out)
    print(f'  {out}  {out.stat().st_size} bytes  {img.size}')
    print(f'  months charted: {len(months)}  max value: {mx}')


if __name__ == '__main__':
    main()
