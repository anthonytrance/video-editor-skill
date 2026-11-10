"""Contact sheet of labelled frames in one FFmpeg run.

  sheet.py clip.mp4 --times 1,4.5,9 --out s.png        chosen moments
  sheet.py clip.mp4 --every 2 --out s.png              one frame every 2 seconds
  sheet.py render.mp4 --plan edit.json --out s.png     start, middle and end of every shot in a render
  sheet.py a.mp4@3 b.mp4@10.5 c.mp4@2 --out s.png      moments from several files (candidate comparison)
Add --grid N to draw N vertical guide lines (crop planning), --crop 9:16 to frame sources as they would render.
"""
import argparse
import math
import subprocess
import sys
from pathlib import Path

from common import binary, crop_xy, load, probe

FONT = 'C\\:/Windows/Fonts/arial.ttf'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('inputs', nargs='+', help='a file, or file@seconds items')
    ap.add_argument('--out', required=True)
    ap.add_argument('--times', help='comma-separated seconds')
    ap.add_argument('--every', type=float)
    ap.add_argument('--plan', help='edit plan whose render this is: samples each shot')
    ap.add_argument('--width', type=int, default=0, help='tile width in pixels (default 270 vertical, 512 landscape)')
    ap.add_argument('--cols', type=int, default=0)
    ap.add_argument('--grid', type=int, default=0, help='vertical guide lines across each tile')
    ap.add_argument('--crop', help='frame sources to this ratio around --cx, e.g. 9:16')
    ap.add_argument('--cx', type=float, default=0.5)
    a = ap.parse_args()

    items = []  # (file, seconds, label)
    if a.plan:
        plan = load(a.plan)
        for s in plan['shots']:
            for name, t in (('a', s['start'] + 0.05), ('m', (s['start'] + s['end']) / 2), ('z', s['end'] - 0.08)):
                items.append((a.inputs[0], t, f"{s['index']}{name} {t:.1f}s"))
    elif '@' in a.inputs[0]:
        for spec in a.inputs:
            f, t = spec.rsplit('@', 1)
            items.append((f, float(t), f'{Path(f).stem} @ {t}'))
    else:
        f = a.inputs[0]
        if a.times:
            ts = [float(t) for t in a.times.split(',')]
        else:
            step = a.every or max(1.0, probe(f)['duration'] / 12)
            ts = [round(i * step, 2) for i in range(int(probe(f)['duration'] / step) + 1)]
        items = [(f, t, f'{t}s') for t in ts]
    if not items:
        sys.exit('Nothing to sample.')

    first = probe(items[0][0])
    vertical = first['height'] > first['width'] or a.crop
    tw = a.width or (270 if vertical else 512)
    cols = a.cols or (6 if vertical else 3)
    if a.crop:
        rw, rh = map(int, a.crop.split(':'))
        th = round(tw * rh / rw / 2) * 2
    else:
        th = round(tw * first['height'] / first['width'] / 2) * 2
    args = [binary('ffmpeg'), '-v', 'error', '-y']
    fc = []
    for i, (f, t, label) in enumerate(items):
        args += ['-ss', f'{max(0, t):.3f}', '-i', f]
        chain = f'[{i}:v]trim=end_frame=1,setpts=PTS-STARTPTS,'
        if a.crop:
            rw, rh = map(int, a.crop.split(':'))
            ww, wh, x, y = crop_xy(probe(f), rw, rh, a.cx)
            chain += f'crop={ww}:{wh}:{x}:{y},'
        chain += f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        if a.grid:
            chain += f",drawgrid=w={tw / a.grid:.2f}:h=0:t=1:c=white@0.4"
        chain += (f",drawtext=fontfile='{FONT}':text='{label.replace(':', ' ')}':x=6:y=6:fontsize={max(14, tw // 14)}"
                  f":fontcolor=yellow:box=1:boxcolor=black@0.8[t{i}]")
        fc.append(chain)
    n = len(items)
    rows = math.ceil(n / cols)
    fc.append(''.join(f'[t{i}]' for i in range(n)) + f'concat=n={n}:v=1:a=0,'
              f'tile={cols}x{rows}:padding=2:color=black')
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    args += ['-filter_complex', ';'.join(fc), '-frames:v', '1', str(out)]
    r = subprocess.run(args, capture_output=True, text=True, errors='replace')
    if r.returncode:
        sys.exit(r.stderr[-1500:])
    print(f'{out} ({n} frames, {cols}x{rows})')


if __name__ == '__main__':
    main()
