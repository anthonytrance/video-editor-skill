"""Render an edit plan (edit.json) to an MP4 with one FFmpeg run. The checker runs first and blocks on errors."""
import argparse
import sys
from pathlib import Path

from common import EXTRAS, GRADES, PlanError, binary, crop_xy, load, probe, when
import validate

SMOOTH = '(3*{q}*{q}-2*{q}*{q}*{q})'  # ease in and out


def esc_path(p):
    return "'" + str(p).replace('\\', '/').replace(':', '\\:') + "'"


def esc_text(t):
    return "'" + str(t).replace('\\', '\\\\').replace("'", '\u2019').replace(':', '\\:').replace('%', '\\%') + "'"


def shot_video(i, s, plan, draft):
    cw, ch, fps = plan['_cw'], plan['_ch'], plan['_fps']
    info = probe(s['src'])
    fr = dict(s.get('frame', {}))
    move = fr.get('move', 'still')
    n = s['f1'] - s['f0']
    D = s['dur']
    speed = s.get('speed', 1.0)
    head = f"[{i}:v]setpts=PTS/{speed},fps={fps},trim=end_frame={n},setpts=PTS-STARTPTS,"
    cx, cy = fr.get('cx', 0.5), fr.get('cy', 0.5)
    if move == 'fit':
        ww, wh, x, y = crop_xy(info, cw, ch, cx if not isinstance(cx, list) else cx[0], 0.5)
        chain = (head + f"split[f{i}][b{i}];[b{i}]crop={ww}:{wh}:{x}:{y},scale={cw // 2}:{ch // 2},boxblur=18:3,"
                 f"scale={cw}:{ch},eq=brightness=-0.10[bb{i}];"
                 f"[f{i}]scale={cw}:{ch}:force_original_aspect_ratio=decrease:force_divisible_by=2[ff{i}];"
                 f"[bb{i}][ff{i}]overlay=(W-w)/2:(H-h)/2,")
    elif move == 'pan':
        xs = cx if isinstance(cx, list) else [cx, cx]
        ys = cy if isinstance(cy, list) else [cy, cy]
        ww, wh, x0, y0 = crop_xy(info, cw, ch, xs[0], ys[0])
        _, _, x1, y1 = crop_xy(info, cw, ch, xs[1], ys[1])
        q = SMOOTH.format(q=f'min(1\\,t/{D:.3f})')
        chain = head + (f"crop={ww}:{wh}:x='{x0}+({x1}-{x0})*{q}':y='{y0}+({y1}-{y0})*{q}',"
                        f"scale={cw}:{ch},")
    else:
        ww, wh, x, y = crop_xy(info, cw, ch, cx, cy)
        z = fr.get('zoom', {'push': 1.06, 'pull': 1.06, 'punch': 1.12}.get(move, 1.0))
        Z = {'still': None,
             'push': f'(1+{z - 1:.4f}*t/{D:.3f})',
             'pull': f'({z:.4f}-{z - 1:.4f}*t/{D:.3f})',
             'punch': f'(1+{z - 1:.4f}*max(0\\,1-t/{fr.get("decay", 0.4)}))'}[move]
        chain = head + f"crop={ww}:{wh}:{x}:{y},"
        if Z:
            chain += (f"scale=w='trunc({cw}*{Z}/2)*2':h='trunc({ch}*{Z}/2)*2':eval=frame,"
                      f"crop={cw}:{ch},")
        else:
            chain += f"scale={cw}:{ch},"
    extras = s.get('extra', [])
    extras = [extras] if isinstance(extras, str) else extras
    look = [EXTRAS.get(e, e) for e in extras]
    grade = s.get('grade')
    g = plan['_grade'] if grade is None else GRADES.get(grade, grade)
    tail = ','.join(f for f in ['setsar=1', *look, g] if f)
    if draft:
        tail += f',scale={cw // 2}:{ch // 2}'
    return chain + tail + f'[v{i}]'


def build(plan, out, draft=False):
    cw, ch, fps, total = plan['_cw'], plan['_ch'], plan['_fps'], plan['_total']
    args = [binary('ffmpeg'), '-v', 'error', '-y']
    fc, k = [], 0
    shots = plan['shots']
    for s in shots:
        speed = s.get('speed', 1.0)
        args += ['-ss', f"{s['in']:.3f}", '-t', f"{s['dur'] * speed + 1:.3f}", '-i', s['src']]
    for i, s in enumerate(shots):
        fc.append(shot_video(i, s, plan, draft))
    k = len(shots)
    fc.append(''.join(f'[v{i}]' for i in range(k)) + f'concat=n={k}:v=1:a=0[cat]')
    cur = 'cat'
    scale = 0.5 if draft else 1.0

    # Overlays, in plan order (later ones sit on top).
    texts = []
    for o in plan.get('overlays', []):
        t0, t1 = when(o.get('t', [0, None])[0], plan), when(o.get('t', [0, None])[1], plan)
        fin, fout = o.get('fade', 0.3), o.get('fade_out', 0.1)
        if 'text' in o:
            texts.append((o, t0, t1, fin, fout))
            continue
        nxt = f'o{len(fc)}'
        if 'dim' in o:
            lab = f'dm{len(fc)}'
            fc.append(f"color=black:s={cw}x{ch}:r={fps}:d={t1 - t0 + 0.1:.3f},format=yuva420p,"
                      f"colorchannelmixer=aa={o['dim']},fade=t=in:st=0:d={fin}:alpha=1,"
                      f"{'scale=%d:%d,' % (cw // 2, ch // 2) if draft else ''}setpts=PTS-STARTPTS+{t0:.3f}/TB[{lab}]")
            fc.append(f'[{cur}][{lab}]overlay=0:0:eof_action=pass[{nxt}]')
        else:
            src = o.get('image') or o.get('video')
            still = Path(src).suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')
            args += (['-loop', '1', '-t', f'{t1 - t0:.3f}', '-i', src] if still
                     else ['-ss', str(o.get('ss', 0)), '-t', f'{t1 - t0:.3f}', '-i', src])
            idx = len([a for a in args if a == '-i']) - 1
            w = round(o.get('width', cw // 2) * scale)
            f = f"[{idx}:v]fps={fps},"
            if o.get('crop'):
                f += f"crop={o['crop']},"
            f += f"scale={w}:-1,format=yuva420p,fade=t=in:st=0:d={fin}:alpha=1,"
            if t1 < total - 0.01:
                f += f"fade=t=out:st={max(0, t1 - t0 - fout):.3f}:d={fout}:alpha=1,"
            f += f"setpts=PTS-STARTPTS+{t0:.3f}/TB[im{idx}]"
            fc.append(f)
            x = '(W-w)/2' if o.get('x', 'center') == 'center' else str(round(o['x'] * scale))
            fc.append(f"[{cur}][im{idx}]overlay={x}:{round(o.get('y', 0) * scale)}:eof_action=pass[{nxt}]")
        cur = nxt
    if texts:
        parts = []
        for o, t0, t1, fin, fout in texts:
            font = o.get('font') or plan['_brand'].get('assets', {}).get('regular', 'C:/Windows/Fonts/arial.ttf')
            alpha = (f"alpha='min(1\\,max(0\\,(t-{t0:.3f})/{fin}))*min(1\\,max(0\\,({t1:.3f}-t)/{fout}))'")
            x = '(w-tw)/2' if o.get('x', 'center') == 'center' else str(round(o['x'] * scale))
            sh = o.get('shadow', True)
            parts.append(f"drawtext=fontfile={esc_path(font)}:text={esc_text(o['text'])}:"
                         f"fontsize={round(o.get('size', 56) * scale)}:fontcolor={o.get('color', 'white')}:"
                         f"x={x}:y={round(o['y'] * scale)}:{alpha}"
                         + (':shadowcolor=black@0.55:shadowx=2:shadowy=2' if sh else '')
                         + (f":box=1:boxcolor={o['box']}:boxborderw={o.get('pad', 18)}" if o.get('box') else ''))
        fc.append(f'[{cur}]' + ','.join(parts) + '[txt]')
        cur = 'txt'
    if plan.get('captions', {}).get('file'):
        fc.append(f"[{cur}]subtitles={esc_path(plan['captions']['file'])}[cap]")
        cur = 'cap'

    # Audio: shot sound (voices, ambience) on one bus, music under it, ducked while the bus is active.
    voice = []
    for i, s in enumerate(shots):
        if s.get('audio_db') is None:
            continue
        D, speed = s['dur'], s.get('speed', 1.0)
        tempo = f',atempo={speed}' if speed != 1.0 else ''
        ms = round(s['start'] * 1000)
        fc.append(f"[{i}:a]atrim=0:{D * speed:.3f},asetpts=PTS-STARTPTS{tempo},volume={s['audio_db']}dB,"
                  f"afade=t=in:d={s.get('afade', 0.03)},afade=t=out:st={max(0, D - s.get('afade', 0.03)):.3f}:d={s.get('afade', 0.03)},"
                  f"aresample=48000,adelay={ms}|{ms}[sa{i}]")
        voice.append(f'[sa{i}]')
    music = plan.get('music')
    mix = []
    if voice:
        fc.append(''.join(voice) + f'amix=inputs={len(voice)}:normalize=0:dropout_transition=0[vox]')
    if music:
        args += ['-ss', str(music.get('start', 0)), '-t', f'{total:.3f}', '-i', music['file']]
        mi = len([a for a in args if a == '-i']) - 1
        fc.append(f"[{mi}:a]aresample=48000,volume={music.get('gain_db', 0)}dB[mus]")
        if voice and music.get('duck', True):
            fc.append('[vox]asplit[vox1][vox2]')
            d = music.get('duck_ratio', 8)
            fc.append(f'[mus][vox2]sidechaincompress=threshold=0.02:ratio={d}:attack=20:release=400[mduck]')
            mix = ['[mduck]', '[vox1]']
        else:
            mix = ['[mus]'] + (['[vox]'] if voice else [])
    elif voice:
        mix = ['[vox]']
    if mix:
        fc.append(''.join(mix) + (f'amix=inputs={len(mix)}:normalize=0:dropout_transition=0,' if len(mix) > 1 else 'anull,')
                  + f"apad,atrim=0:{total:.3f},afade=t=out:st={max(0, total - plan.get('fade_out', 0.6)):.3f}:d={plan.get('fade_out', 0.6)}"
                  + (f",loudnorm=I={plan['loudnorm']}:TP=-1:LRA=11" if plan.get('loudnorm') else '')
                  + ',aresample=48000[a]')
    else:
        fc.append(f'anullsrc=r=48000:cl=stereo,atrim=0:{total:.3f}[a]')

    args += ['-filter_complex', ';'.join(fc), '-map', f'[{cur}]', '-map', '[a]', '-t', f'{total:.3f}',
             '-c:v', 'libx264', '-preset', 'veryfast' if draft else 'slow', '-crf', '28' if draft else str(plan.get('crf', 18)),
             '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-r', str(fps),
             '-c:a', 'aac', '-b:a', '128k' if draft else '320k', '-movflags', '+faststart', str(out)]
    return args


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('plan')
    ap.add_argument('--out', required=True)
    ap.add_argument('--draft', action='store_true', help='half size, fast encode, for checking cuts and framing')
    ap.add_argument('--force', action='store_true', help='overwrite an existing output')
    ap.add_argument('--print', action='store_true', help='print the FFmpeg command and stop')
    a = ap.parse_args()
    import subprocess
    try:
        plan = load(a.plan)
        errors, warnings = validate.check(plan)
    except PlanError as e:
        sys.exit(f'Plan error: {e}')
    for w in warnings:
        print('WARNING', w)
    if errors:
        for e in errors:
            print('ERROR', e)
        sys.exit('Not rendered: fix the errors above.')
    out = Path(a.out).resolve()
    if out.exists() and not a.force:
        sys.exit(f'{out} exists. Choose a new name or pass --force.')
    out.parent.mkdir(parents=True, exist_ok=True)
    args = build(plan, out, a.draft)
    if a.print:
        print(subprocess.list2cmdline(args))
        return
    r = subprocess.run(args)
    if r.returncode:
        sys.exit(r.returncode)
    mb = out.stat().st_size / 1e6
    print(f'Rendered {out} ({mb:.1f} MB, {plan["_total"]:.2f}s, {len(plan["shots"])} shots)')
    if not a.draft:
        errs, warns = validate.check_render(plan, out)
        for w in warns:
            print('WARNING', w)
        for e in errs:
            print('ERROR', e)


if __name__ == '__main__':
    main()
