"""Delivery report: the facts about a finished render, in plain text, to send with every delivery.

  report.py edit.json out/v1.mp4

It states what a machine can know: file, destination, colour, music, loudness, every shot with its note, every
on-screen text with its times, extra sound, and what the checker still warns about. Add in your own words what the
contact sheet shows; never send a render without this report.
"""
import argparse
import sys
from pathlib import Path

from common import PlanError, load, picture_box, probe, when
import validate


def length(s, plan):
    bpm = plan['_bpm']
    if bpm and s.get('audio_db') is None:
        bars = s['dur'] * bpm / 240
        near = round(bars * 2) / 2  # cuts sit on whole frames, so a bar is never exact to the last decimal
        if near and abs(bars - near) < 0.03:
            return f'{near:g} bar' + ('' if near == 1 else 's')
    return f"{s['dur']:.2f}s"


def build(plan, out):
    lines = []
    add = lines.append
    info = probe(out)
    shots = plan['shots']
    add(f"Delivery report: {plan.get('title', Path(out).stem)}")
    add(f"File: {Path(out).name}, {Path(out).stat().st_size / 1e6:.1f} MB, {info['duration']:.1f} seconds, "
        f"{info['width']}x{info['height']}, {info['fps']:.4g} fps.")
    dest = plan.get('destination')
    framed = [s['index'] for s in shots if picture_box(s, plan)]
    design = ('full screen picture throughout' if not framed else
              'framed picture on a designed background throughout' if len(framed) == len(shots) else
              f"framed picture on shots {', '.join(map(str, framed))}, full screen on the others")
    add(f"Destination: {dest or 'not named in the plan'}. Design: {design}.")
    grade = plan.get('grade', plan['_brand'].get('grade', 'none'))
    own = [f"shot {s['index']} {s.get('grade') or ''} {s.get('extra') or ''}".replace('  ', ' ').strip()
           for s in shots if s.get('grade') or s.get('extra')]
    add('Colour: ' + ('no colour correction applied' if grade in ('none', '') and not own else
                      f'grade "{grade}" on every shot' + (f"; adjusted on {'; '.join(own)}" if own else '')) + '.')
    hdr = sorted({Path(s['src']).name for s in shots if probe(s['src']).get('hdr')})
    if hdr:
        add(f"HDR footage converted to normal video: {', '.join(hdr)}.")
    music = plan.get('music')
    if music:
        add(f"Music: {Path(music['file']).stem}, from {music.get('start', 0):.1f}s of the track"
            + (f", {music['bpm']} BPM" if music.get('bpm') else '') + f", level {music.get('gain_db', 0):+g} dB.")
    else:
        add('Music: none.')
    voiced = [s for s in shots if s.get('audio_db') is not None]
    if voiced:
        add('Shot sound kept: ' + ', '.join(
            f"shot {s['index']} at {s['audio_db']:+g} dB" + ('' if s.get('duck', True) else ' (on top of the music)')
            for s in voiced) + '.')
    for k, a in enumerate(plan.get('sound', []), 1):
        add(f"Extra sound {k}: {Path(a['src']).name} from {a.get('in', 0):.1f}s, plays {a['_at']:.2f}s to "
            f"{a['_at'] + a['_len']:.2f}s at {a.get('db', 0):+g} dB"
            + (', music dips under it.' if a.get('duck', True) else ', on top of the music.'))
    lufs, peak = validate.loudness(out) if info['audio'] else (None, None)
    add(f'Loudness: {lufs} LUFS, true peak {peak:+.1f} dB.' if peak is not None else 'Loudness: no sound track.')
    add('')
    add(f'Shots ({len(shots)}):')
    for s in shots:
        fr = s.get('frame', {})
        slow = f", speed {s['speed']}" if s.get('speed', 1.0) != 1.0 else ''
        add(f"{s['index']}. {s['start']:.2f}s to {s['end']:.2f}s ({length(s, plan)}), {Path(s['src']).name} from "
            f"{s['in']:.1f}s, {fr.get('move', 'still')}{slow}: {s.get('note', 'NO NOTE')}")
    texts = [o for o in plan.get('overlays', []) if 'text' in o]
    other = [o for o in plan.get('overlays', []) if 'text' not in o]
    span = lambda o: (when(o.get('t', [0, None])[0], plan), when(o.get('t', [0, None])[1], plan))
    add('')
    add('Text on screen:' if texts else 'Text on screen: none.')
    for o in texts:
        add(f'"{o["text"]}" from {span(o)[0]:.2f}s to {span(o)[1]:.2f}s.')
    if other:
        add('')
        add('Graphics:')
        for o in other:
            what = (f"picture dimmed to {round((1 - o['dim']) * 100)}%" if 'dim' in o
                    else Path(o.get('image') or o.get('video')).stem)
            add(f'{what} from {span(o)[0]:.2f}s to {span(o)[1]:.2f}s.')
    if plan.get('captions', {}).get('file'):
        add(f"Captions burned in from {Path(plan['captions']['file']).name}.")
    errors, warnings = validate.check(plan)
    e2, w2 = validate.check_render(plan, out)
    add('')
    notes = [f'ERROR: {e}' for e in errors + e2] + warnings + w2
    add('Checker: nothing to report.' if not notes else 'Checker still reports:')
    lines.extend(notes)
    add('')
    add('Not checked by a machine: whether each shot shows what its note says, faces and names, spelling of names, '
        'and whether the edit feels right. Say what you verified on the contact sheet and what a sighted person '
        'should still confirm before publishing.')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('plan')
    ap.add_argument('render')
    a = ap.parse_args()
    try:
        print(build(load(a.plan), a.render))
    except PlanError as e:
        sys.exit(f'Plan error: {e}')


if __name__ == '__main__':
    main()
