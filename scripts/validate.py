"""Check an edit plan before rendering, and a finished render after it.

Errors block the render: reused footage, boxed shots in a full-screen edit without permission, text outside the
safe area, shots running past their source, music too short. Warnings need a human decision: shots that look alike,
moments of one clip close together, cuts off the beat, black bars inside the source, black frames in the render.
"""
import argparse
import itertools
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import MOVES, PlanError, binary, crop_xy, load, picture_box, probe, target, when


def _frame_bits(s, plan):
    """64-bit difference hash plus mean colour of the middle frame, cropped the way it will render."""
    info = probe(s['src'])
    fr = s.get('frame', {})
    cx, cy = fr.get('cx', 0.5), fr.get('cy', 0.5)
    cx = sum(cx) / 2 if isinstance(cx, list) else cx
    cy = sum(cy) / 2 if isinstance(cy, list) else cy
    ww, wh, x, y = crop_xy(info, *target(s, plan), cx, cy)
    t = s['in'] + s['dur'] * s.get('speed', 1.0) / 2
    raw = subprocess.run([binary('ffmpeg'), '-v', 'error', '-ss', f'{t:.3f}', '-i', s['src'], '-frames:v', '1',
                          '-vf', f'crop={ww}:{wh}:{x}:{y},scale=9:8:flags=area', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'],
                         capture_output=True, check=True).stdout
    px = [raw[i:i + 3] for i in range(0, len(raw), 3)]
    lum = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in px]
    bits = [lum[r * 9 + c] > lum[r * 9 + c + 1] for r in range(8) for c in range(8)]
    colour = [sum(p[k] for p in px) / len(px) for k in range(3)]
    return bits, colour


def lookalikes(plan, limit_bits=16, limit_colour=30):
    shots = plan['shots']
    with ThreadPoolExecutor(6) as ex:
        sig = list(ex.map(lambda s: _frame_bits(s, plan), shots))
    found = []
    for a, b in itertools.combinations(range(len(shots)), 2):
        ham = sum(x != y for x, y in zip(sig[a][0], sig[b][0]))
        col = sum((x - y) ** 2 for x, y in zip(sig[a][1], sig[b][1])) ** 0.5
        if ham <= limit_bits and col <= limit_colour:
            found.append((a + 1, b + 1, ham, round(col)))
    return found


def _bars(src, t0, dur, region=None):
    """Bounding box of non-black picture over a stretch, via cropdetect. Returns (w, h, x, y) or None."""
    vf = 'select=not(mod(n\\,6)),cropdetect=limit=16:round=2:reset=0'
    if region:
        vf = f'crop={region},' + vf
    r = subprocess.run([binary('ffmpeg'), '-v', 'info', '-ss', f'{t0:.3f}', '-t', f'{dur:.3f}', '-i', str(src),
                        '-vf', vf, '-an', '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
    hits = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', r.stderr)
    return tuple(map(int, hits[-1])) if hits else None


def _text_box(o):
    from PIL import ImageFont
    font = ImageFont.truetype(o['font'] or 'C:/Windows/Fonts/arial.ttf', round(o.get('size', 56)))
    l, t, r, b = font.getbbox(o['text'])
    return r - l, b


def check(plan, looks=True, bars=True):
    errors, warnings = [], []
    cw, ch, fps, total = plan['_cw'], plan['_ch'], plan['_fps'], plan['_total']
    safe = plan['_safe']
    shots = plan['shots']
    dest = plan['_dest']
    if dest.get('max_s') and total > dest['max_s']:
        errors.append(f"{plan['destination']} videos can be at most {dest['max_s']}s; this edit is {total:.1f}s.")
    if dest.get('full_screen') and abs(cw / ch - 9 / 16) > 0.01:
        warnings.append(f"{plan['destination']} plays full screen at 9:16; a {cw}x{ch} canvas gets blank space around it. "
                        'For a square or 4:5 look keep a 9:16 canvas and use a "picture" box with a designed background.')
    for s in shots:
        n = f"shot {s['index']}"
        box = picture_box(s, plan)
        if box and (box['x'] < 0 or box['y'] < 0 or box['x'] + box['w'] > cw or box['y'] + box['h'] > ch):
            errors.append(f"{n}: the picture box {box['w']}x{box['h']} at {box['x']},{box['y']} does not fit the {cw}x{ch} canvas.")
        if not Path(s['src']).exists():
            errors.append(f"{n}: source {s['src']} not found.")
            continue
        info = probe(s['src'])
        need = s['dur'] * s.get('speed', 1.0)
        if s['in'] < 0 or s['in'] + need > info['duration'] + 0.05:
            errors.append(f"{n}: needs {s['in']:.2f}s to {s['in'] + need:.2f}s but {Path(s['src']).name} is {info['duration']:.2f}s long.")
        if s['dur'] <= 0:
            errors.append(f'{n}: has no length.')
        move = s.get('frame', {}).get('move', 'still')
        if move not in MOVES:
            errors.append(f"{n}: unknown move {move!r}; use one of {', '.join(sorted(MOVES))}.")
        if move == 'fit' and not plan.get('allow_fit'):
            errors.append(f'{n}: "fit" puts a boxed picture on a blurred background, which mixes aspect ratios. '
                          'Use a filling move, or set "allow_fit": true if the owner chose that look.')
        if s.get('audio_db') is not None and not info['audio']:
            errors.append(f'{n}: audio_db is set but the source has no sound.')
        if s.get('audio_db') is not None and not 0.5 <= s.get('speed', 1.0) <= 2:
            errors.append(f'{n}: sound can only follow a speed between 0.5 and 2; mute it instead.')
    # Reused footage: the same stretch of a source in two shots.
    by_src = {}
    for s in shots:
        by_src.setdefault(s['src'], []).append(s)
    gap = plan.get('min_gap', 2.0)
    for src, group in by_src.items():
        group.sort(key=lambda s: s['in'])
        for a, b in zip(group, group[1:]):
            a_end = a['in'] + a['dur'] * a.get('speed', 1.0)
            if b['in'] < a_end - 1 / fps:
                errors.append(f"shots {a['index']} and {b['index']} reuse the same footage of {Path(src).name} "
                              f"({b['in']:.2f}s to {min(a_end, b['in'] + b['dur']):.2f}s).")
            elif b['in'] - a_end < gap:
                warnings.append(f"shots {a['index']} and {b['index']} are only {b['in'] - a_end:.1f}s apart in "
                                f"{Path(src).name}, so they may read as the same moment.")
    # Text and graphics inside the safe area.
    for o in plan.get('overlays', []):
        try:
            t0, t1 = when(o.get('t', [0, None])[0], plan), when(o.get('t', [0, None])[1], plan)
        except PlanError as e:
            errors.append(str(e))
            continue
        label = o.get('text') or Path(str(o.get('image') or o.get('video') or 'dim')).name
        if not (0 <= t0 < t1 <= total + 0.01):
            errors.append(f'overlay {label!r}: times {t0:.2f} to {t1:.2f} fall outside the {total:.2f}s edit.')
        if o.get('safe_ok') or 'dim' in o:
            continue
        if 'text' in o:
            w, h = _text_box(o)
            x = (cw - w) / 2 if o.get('x', 'center') == 'center' else o['x']
            box = (x, o['y'], x + w, o['y'] + h)
            kind = errors
        else:
            src = o.get('image') or o.get('video')
            if not Path(src).exists():
                errors.append(f'overlay {label!r}: file not found.')
                continue
            info = probe(src)
            iw, ih = (map(int, o['crop'].split(':')[:2]) if o.get('crop') else (info['width'], info['height']))
            w = o.get('width', cw // 2)
            h = w * ih / iw
            x = (cw - w) / 2 if o.get('x', 'center') == 'center' else o['x']
            box = (x, o.get('y', 0), x + w, o.get('y', 0) + h)
            kind = warnings
        bad = []
        if box[1] < safe['top']:
            bad.append(f"top edge {box[1]:.0f}px is above the {safe['top']}px line")
        if box[3] > ch - safe['bottom']:
            bad.append(f"bottom edge {box[3]:.0f}px is below the {ch - safe['bottom']}px line")
        if box[0] < safe['side'] or box[2] > cw - safe['side']:
            bad.append(f"it is {box[2] - box[0]:.0f}px wide and reaches the side margins")
        if bad:
            kind.append(f"overlay {label!r} leaves the safe area: {'; '.join(bad)}.")
    # Music.
    music = plan.get('music')
    if music:
        if not Path(music['file']).exists():
            errors.append(f"music {music['file']} not found.")
        else:
            left = probe(music['file'])['duration'] - music.get('start', 0)
            if left < total - 0.05:
                errors.append(f'music has {left:.2f}s left after its start point; the edit needs {total:.2f}s.')
        bpm = plan['_bpm']
        if bpm and plan.get('cut_on_beat', True):
            beat = 60 / bpm
            for s in shots[1:]:
                off = s['start'] - round(s['start'] / beat) * beat
                if abs(off) > 1.5 / fps:
                    warnings.append(f"shot {s['index']} starts at {s['start']:.2f}s, {off * 1000:+.0f}ms off the beat.")
    if plan.get('captions', {}).get('file') and not Path(plan['captions']['file']).exists():
        errors.append('captions file not found.')
    if errors:
        return errors, warnings
    if looks:
        for a, b, ham, col in lookalikes(plan):
            warnings.append(f'shots {a} and {b} look alike (picture difference {ham}/64, colour difference {col}). '
                            'Check they are not the same moment or angle.')
    if bars:
        for s in shots:
            info = probe(s['src'])
            fr = s.get('frame', {})
            cx = fr.get('cx', 0.5)
            cx = cx if not isinstance(cx, list) else cx[0]
            ww, wh, x, y = crop_xy(info, *target(s, plan), cx, fr.get('cy', 0.5) if not isinstance(fr.get('cy'), list) else 0.5)
            got = _bars(s['src'], s['in'], min(s['dur'] * s.get('speed', 1.0), 6), f'{ww}:{wh}:{x}:{y}')
            if got and (got[0] < ww * 0.96 or got[1] < wh * 0.96):
                warnings.append(f"shot {s['index']}: the framed picture has black edges ({got[0]}x{got[1]} of {ww}x{wh}). "
                                'The source may have bars baked in; reframe or zoom past them.')
    return errors, warnings


def check_render(plan, out):
    errors, warnings = [], []
    info = probe(out)
    cw, ch, total = plan['_cw'], plan['_ch'], plan['_total']
    if (info['width'], info['height']) != (cw, ch):
        errors.append(f"render is {info['width']}x{info['height']}, plan says {cw}x{ch}.")
    if abs(info['duration'] - total) > 0.1:
        warnings.append(f"render is {info['duration']:.2f}s, plan says {total:.2f}s.")
    if not info['audio']:
        errors.append('render has no sound track.')
    for s in plan['shots']:
        box = picture_box(s, plan)
        region = f"{box['w']}:{box['h']}:{box['x']}:{box['y']}" if box else None
        pw, ph = target(s, plan)
        got = _bars(out, s['start'] + 0.05, max(0.1, s['dur'] - 0.1), region)
        if got and (got[0] < pw * 0.95 or got[1] < ph * 0.95):
            warnings.append(f"shot {s['index']} ({s['start']:.1f}s to {s['end']:.1f}s) may have black bars: "
                            f"picture area {got[0]}x{got[1]} of {pw}x{ph}.")
    r = subprocess.run([binary('ffmpeg'), '-v', 'info', '-i', str(out), '-vf', 'blackdetect=d=0.15:pix_th=0.06',
                        '-an', '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
    for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', r.stderr):
        warnings.append(f'black picture from {float(a):.2f}s to {float(b):.2f}s.')
    mb = Path(out).stat().st_size / 1e6
    limit = plan.get('max_mb')
    if limit and mb > limit:
        warnings.append(f'render is {mb:.1f} MB, over the {limit} MB limit in the plan.')
    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan')
    ap.add_argument('--render', help='also check this finished file')
    ap.add_argument('--no-looks', action='store_true', help='skip the look-alike comparison')
    ap.add_argument('--no-bars', action='store_true', help='skip the black-edge scan of sources')
    a = ap.parse_args()
    try:
        plan = load(a.plan)
        errors, warnings = check(plan, looks=not a.no_looks, bars=not a.no_bars)
        if a.render:
            e2, w2 = check_render(plan, a.render)
            errors += e2
            warnings += w2
    except PlanError as e:
        sys.exit(f'Plan error: {e}')
    print(f"{len(plan['shots'])} shots, {plan['_total']:.2f}s, canvas {plan['_cw']}x{plan['_ch']}.")
    for w in warnings:
        print('WARNING', w)
    for e in errors:
        print('ERROR', e)
    print('OK' if not errors else f'{len(errors)} error(s).')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
