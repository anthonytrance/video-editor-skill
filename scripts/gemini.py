"""Gemini, through OpenRouter, as footage logger and render critic. It watches and listens.

  gemini.py log WORKDIR clip1.mp4 clip2.mp4 --context brief.txt [--ratio 9:16]
      Makes a small proxy of each clip with a burned-in timecode (WORKDIR/proxy) and writes a moment log per clip
      (WORKDIR/log/NAME.json): who is where, what happens, energy, sound, speech, quality, best crop centre.
  gemini.py review render.mp4 --context brief.txt [--plan edit.json] [--out review.json]
      Blunt critique of a finished edit: hook, arc, pacing, repeats, framing, text, colour, sound.

The context file says who and what is in the footage (names and how to recognise them, event, purpose).
Gemini's notes are leads, not facts: check every claim against frames or the plan before acting on it.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import requests

from common import api_key, binary, load, probe

MODEL = os.environ.get('VIDEO_EDITOR_GEMINI', 'google/gemini-3.8-flash')
API = 'https://openrouter.ai/api/v1/chat/completions'
TC = "drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='T=%{eif\\:n/10\\:d}.%{eif\\:mod(n\\,10)\\:d}s':x=8:y=8:fontsize=24:fontcolor=yellow:box=1:boxcolor=black"

LOG_PROMPT = """You are logging raw footage for a short video edit.

CONTEXT FROM THE OWNER:
{context}

The edit is {ratio}. A {ratio} window cut from this {w}x{h} source shows about {frac:.0%} of its {axis}.
For every moment report where the key subjects sit along that axis as a fraction 0.0 to 1.0
(0 = left/top edge, 1 = right/bottom edge).

Watch AND listen to the whole clip. Return ONLY JSON:
{{"summary": str,
 "camera": str,
 "moments": [
  {{"start": float, "end": float,
   "people": [{{"who": str, "x": float, "face_visible": bool, "doing": str}}],
   "action": str,
   "emotion": str,
   "energy": int,
   "sound": str,
   "speech": str,
   "quality": str,
   "fits": bool,
   "crop_center": float,
   "use_for": str}}
 ]}}
"who": a name from the context when you are sure, otherwise CROWD, OTHER or UNKNOWN. Never guess a name.
"sound": what is heard (music, cheering, singing along, speech, wind, traffic, silence).
"speech": the words spoken in this moment, or "" if none.
"quality": sharp / soft / blurry / dark / shaky / overexposed / noisy.
"fits": can one {ratio} window hold the key subjects without cutting heads?
"use_for": opener / peak / build / reaction / talking / establishing / closer / filler / avoid.
Moments are 2 to 6 seconds and cover the whole clip.

TIMING: a yellow timecode "T=xx.xs" is burned into the top-left of every frame. It is the true clip time.
Read every start and end from it, never estimate. The clip is exactly {dur:.1f} seconds long; no value may exceed it."""

REVIEW_PROMPT = """You are a senior short-form video editor reviewing an edit before it is published.

CONTEXT FROM THE OWNER:
{context}

FORMAT: {w}x{h}, {dur:.1f} seconds.{ui}
{shots}
A yellow timecode is burned into the top-left for reference only; it is not part of the edit.

Watch and listen. Be blunt and specific and cite timecodes. Report only problems you actually see or hear;
an empty list is a valid answer. Return ONLY JSON:
{{"overall_score": int,
 "hook_first_3s": str,
 "arc": str,
 "pacing_and_cuts_vs_sound": str,
 "repeated_or_lookalike_shots": [str],
 "aspect_or_bars": [str],
 "framing_and_clipped_heads": [str],
 "text_readability_and_ui_overlap": [str],
 "colour_and_quality": [str],
 "sound": [str],
 "top_fixes": [str]}}"""


def proxy(src, out):
    info = probe(src)
    scale = 'scale=640:-2' if info['width'] >= info['height'] else 'scale=-2:640'
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [binary('ffmpeg'), '-v', 'error', '-y', '-i', str(src), '-vf', f'{scale},fps=10,{TC}',
           '-c:v', 'libx264', '-crf', '30', '-preset', 'veryfast']
    cmd += ['-c:a', 'aac', '-b:a', '64k', '-ac', '1'] if info['audio'] else ['-an']
    subprocess.run(cmd + [str(out)], check=True)
    return out


def ask(video, prompt):
    data = base64.b64encode(Path(video).read_bytes()).decode()
    body = {'model': MODEL, 'response_format': {'type': 'json_object'},
            'messages': [{'role': 'user', 'content': [
                {'type': 'video_url', 'video_url': {'url': f'data:video/mp4;base64,{data}'}},
                {'type': 'text', 'text': prompt}]}]}
    r = requests.post(API, headers={'Authorization': f'Bearer {api_key()}'}, json=body, timeout=900)
    if r.status_code != 200:
        raise SystemExit(f'OpenRouter {r.status_code}: {r.text[:600]}')
    j = r.json()
    txt = j['choices'][0]['message']['content'].strip().removeprefix('```json').removesuffix('```').strip()
    out = json.loads(txt)
    out['_model'] = j.get('model', MODEL)
    out['_cost'] = (j.get('usage') or {}).get('cost')
    return out


def ratio_numbers(ratio):
    a, b = map(int, ratio.split(':'))
    return a, b


def cmd_log(a):
    work = Path(a.workdir)
    context = Path(a.context).read_text(encoding='utf-8') if a.context else 'No context given.'
    rw, rh = ratio_numbers(a.ratio)
    total = 0.0
    for src in a.clips:
        src = Path(src)
        info = probe(src)
        dest = work / 'log' / f'{src.stem}.json'
        if dest.exists() and not a.force:
            print(f'{src.stem}: log exists, skipped (--force to redo)')
            continue
        if info['width'] / info['height'] > rw / rh:
            frac, axis = info['height'] * rw / rh / info['width'], 'width'
        else:
            frac, axis = info['width'] * rh / rw / info['height'], 'height'
        px = proxy(src, work / 'proxy' / f'{src.stem}.mp4')
        prompt = LOG_PROMPT.format(context=context, ratio=a.ratio, w=info['width'], h=info['height'],
                                   frac=min(1, frac), axis=axis, dur=info['duration'])
        res = ask(px, prompt)
        bad = [m for m in res.get('moments', []) if m.get('end', 0) > info['duration'] + 0.5]
        res['_source'] = str(src.resolve())
        res['_duration'] = info['duration']
        if bad:
            res['_warning'] = f'{len(bad)} moments end after the clip; timing may have drifted.'
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
        total += res['_cost'] or 0
        print(f"{src.stem}: {len(res.get('moments', []))} moments, ${res['_cost'] or 0:.4f}"
              + (f"  WARNING {res['_warning']}" if bad else ''))
    print(f'total ${total:.4f}')


def cmd_review(a):
    context = Path(a.context).read_text(encoding='utf-8') if a.context else 'No context given.'
    info = probe(a.render)
    shots = ''
    if a.plan:
        plan = load(a.plan)
        shots = '\nPLANNED SHOTS:\n' + '\n'.join(
            f"{s['start']:.1f}-{s['end']:.1f}s: {s.get('note') or Path(s['src']).stem}" for s in plan['shots'])
    ui = ''
    if info['height'] > info['width']:
        ui = (' Platform UI covers roughly the top 14%, the bottom 35% and a right-side button rail; '
              'important text and faces should avoid those areas.')
    px = proxy(a.render, Path(a.out).with_suffix('.proxy.mp4'))
    try:
        res = ask(px, REVIEW_PROMPT.format(context=context, w=info['width'], h=info['height'],
                                           dur=info['duration'], ui=ui, shots=shots))
    finally:
        os.remove(px)
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(res, indent=1, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    lg = sub.add_parser('log')
    lg.add_argument('workdir')
    lg.add_argument('clips', nargs='+')
    lg.add_argument('--context')
    lg.add_argument('--ratio', default='9:16')
    lg.add_argument('--force', action='store_true')
    rv = sub.add_parser('review')
    rv.add_argument('render')
    rv.add_argument('--context')
    rv.add_argument('--plan')
    rv.add_argument('--out', required=True)
    a = ap.parse_args()
    {'log': cmd_log, 'review': cmd_review}[a.cmd](a)


if __name__ == '__main__':
    main()
