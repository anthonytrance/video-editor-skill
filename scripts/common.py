"""Shared helpers: probing, the edit plan loader, timeline maths, brand file and API key."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

HOME_STATE = Path(os.environ.get('VIDEO_EDITOR_HOME', Path.home() / '.video-editor'))
HERMES_ENV = Path.home() / 'AppData' / 'Local' / 'hermes' / '.env'

# Named looks. A plan may also give a raw FFmpeg filter string as "grade".
GRADES = {
    'none': '',
    # Dark, hazy club footage: deeper blacks, stronger colour, slight warmth, soft vignette, light sharpening.
    'club': "curves=all='0/0 0.14/0.03 0.5/0.48 0.85/0.88 1/1',eq=saturation=1.35:contrast=1.06,"
            "colorbalance=rs=0.03:bs=-0.02:rh=0.02:bh=-0.03,vignette=PI/5,unsharp=5:5:0.4",
    # Daylight, travel and talking heads: gentle contrast and colour, no vignette.
    'natural': "eq=saturation=1.12:contrast=1.04,unsharp=5:5:0.3",
}
# Shot-level additions, applied before the main grade.
EXTRAS = {
    'warm': 'colorbalance=rs=0.05:gs=0.01:bs=-0.06:rm=0.03:bm=-0.04',
    'cool': 'colorbalance=rs=-0.03:bs=0.04',
    'lift': 'eq=brightness=0.04:gamma=1.08',
}
MOVES = {'still', 'push', 'pull', 'punch', 'pan', 'fit'}
# Phones record HLG or PQ by default; shown as SDR without conversion they look grey and washed out.
HDR_TRANSFERS = {'arib-std-b67', 'smpte2084'}
TONEMAP = ('zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,'
           'zscale=t=bt709:m=bt709:r=tv,format=yuv420p')

# Where the video goes: default canvas, UI-safe area and length limit. A plan's own canvas or safe wins.
# Full-screen destinations show anything that is not 9:16 with blank space around it.
VERTICAL_UI = {'top': 0.14, 'bottom': 0.35, 'side': 0.06}
DESTINATIONS = {
    'reel': {'canvas': [1080, 1920], 'safe': VERTICAL_UI, 'max_s': 900, 'full_screen': True},
    'story': {'canvas': [1080, 1920], 'safe': VERTICAL_UI, 'max_s': 60, 'full_screen': True},
    'tiktok': {'canvas': [1080, 1920], 'safe': VERTICAL_UI, 'full_screen': True},
    'shorts': {'canvas': [1080, 1920], 'safe': VERTICAL_UI, 'max_s': 180, 'full_screen': True},
    'feed': {'canvas': [1080, 1350], 'safe': {'top': 0.04, 'bottom': 0.04, 'side': 0.04}},
    'carousel': {'canvas': [1080, 1350], 'safe': {'top': 0.04, 'bottom': 0.04, 'side': 0.04}, 'max_s': 60},
    'youtube': {'canvas': [1920, 1080], 'safe': {'top': 0.05, 'bottom': 0.1, 'side': 0.05}},
}


class PlanError(ValueError):
    pass


def binary(name):
    found = shutil.which(name)
    if not found:
        raise PlanError(f'{name} is not on PATH.')
    return found


def run(args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace', **kw)


_probe_cache = {}


def probe(path):
    """Duration, display size (rotation applied), fps and audio presence."""
    path = str(Path(path).resolve())
    if path in _probe_cache:
        return _probe_cache[path]
    out = run([binary('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]).stdout
    data = json.loads(out)
    v = next((s for s in data['streams'] if s['codec_type'] == 'video'), None)
    info = {'path': path, 'duration': float(data['format'].get('duration', 0)),
            'audio': any(s['codec_type'] == 'audio' for s in data['streams'])}
    if v:
        w, h = int(v['width']), int(v['height'])
        rot = 0
        for sd in v.get('side_data_list', []):
            rot = int(float(sd.get('rotation', 0) or 0))
        rot = int(v.get('tags', {}).get('rotate', rot) or rot)
        if abs(rot) % 180 == 90:
            w, h = h, w
        num, den = (v.get('avg_frame_rate') or '0/1').split('/')
        info.update(width=w, height=h, fps=float(num) / float(den) if float(den) else 0.0, video=True,
                    hdr=v.get('color_transfer') in HDR_TRANSFERS)
    else:
        info['video'] = False
    _probe_cache[path] = info
    return info


def brand(path=None):
    """Brand file: fonts, logos, default grade and look. Optional; every key has a fallback."""
    p = Path(path) if path else HOME_STATE / 'brand.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def api_key():
    for name in ('OPENROUTER_API_KEY', 'VOICE_OPENROUTER_API_KEY'):
        if os.environ.get(name):
            return os.environ[name]
    if HERMES_ENV.exists():
        found = re.search(r'^OPENROUTER_API_KEY=(.*)$', HERMES_ENV.read_text(encoding='utf-8'), re.M)
        if found:
            return found.group(1).strip().strip('"')
    raise PlanError('No OpenRouter key: set OPENROUTER_API_KEY or add it to the Hermes .env.')


# ---------- plan loading ----------

def safe_zone(cw, ch, given=None):
    """Pixels kept clear of platform UI. Vertical defaults follow Meta's Reels guidance (top 14%, bottom 35%, sides 6%)."""
    if given is None:
        given = {'top': 0.14, 'bottom': 0.35, 'side': 0.06} if ch > cw else {'top': 0.05, 'bottom': 0.1, 'side': 0.05}
    px = lambda v, size: v if v > 1 else round(v * size)
    return {'top': px(given['top'], ch), 'bottom': px(given['bottom'], ch), 'side': px(given['side'], cw)}


def seconds(value, bpm, fps):
    """A length: seconds as a number, or a string like '2bar', '4beat', '1.5s', '36f'."""
    if isinstance(value, (int, float)):
        return float(value)
    m = re.fullmatch(r'\s*([\d.]+)\s*(bar|bars|beat|beats|s|f)\s*', str(value))
    if not m:
        raise PlanError(f'Cannot read length {value!r}. Use seconds, "Nbar", "Nbeat", "Ns" or "Nf".')
    n, unit = float(m.group(1)), m.group(2)
    if unit.startswith(('bar', 'beat')) and not bpm:
        raise PlanError(f'{value!r} needs music.bpm in the plan.')
    return {'bar': n * 4 * 60 / bpm if bpm else 0, 'bars': n * 4 * 60 / bpm if bpm else 0,
            'beat': n * 60 / bpm if bpm else 0, 'beats': n * 60 / bpm if bpm else 0,
            's': n, 'f': n / fps}[unit]


def load(plan_path):
    """Read an edit plan and resolve paths, shot timing (frame-exact) and time references."""
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    base = plan_path.parent
    b = brand(plan.get('brand'))
    resolve = lambda p: str((base / p).resolve()) if p and not Path(p).is_absolute() else p
    dest = plan.get('destination')
    if dest and dest not in DESTINATIONS:
        raise PlanError(f"Unknown destination {dest!r}; use one of {', '.join(DESTINATIONS)}.")
    preset = DESTINATIONS.get(dest, {})
    cw, ch = plan.get('canvas', preset.get('canvas', [1080, 1920]))
    fps = plan.get('fps', 24)
    music = plan.get('music')
    if music:
        music['file'] = resolve(music['file'])
    bpm = music.get('bpm') if music else None
    shots = plan['shots']
    starts, acc = [], 0.0
    total_given = plan.get('duration')
    for i, s in enumerate(shots):
        s['index'] = i + 1
        s['src'] = resolve(s['src'])
        starts.append(acc)
        if s.get('len') == 'rest':
            if total_given is None:
                raise PlanError('A shot with len "rest" needs a plan "duration".')
            s['_len'] = None
        else:
            acc += seconds(s['len'], bpm, fps)
            s['_len'] = acc - starts[-1]
    total = seconds(total_given, bpm, fps) if total_given is not None else acc
    # Frame-exact boundaries, rounded from the musical grid so cuts never drift.
    bounds = [round(t * fps) for t in starts] + [round(total * fps)]
    for i, s in enumerate(shots):
        s['f0'], s['f1'] = bounds[i], bounds[i + 1]
        s['start'], s['end'] = bounds[i] / fps, bounds[i + 1] / fps
        s['dur'] = (bounds[i + 1] - bounds[i]) / fps
    plan['_total'] = bounds[-1] / fps
    if music and music.get('sync'):
        # "This point of the track falls at this point of the edit": the grid then counts from there.
        at = when(music['sync']['at'], plan)
        music['start'] = music['sync']['track'] - at
        music['_grid'] = at
    for a in plan.get('sound', []):
        a['src'] = resolve(a['src'])
        a['_at'] = when(a.get('at', 0), plan)
        a['_len'] = seconds(a['len'], bpm, fps)
    assets = b.get('assets', {})
    for o in plan.get('overlays', []):
        if 'text' in o and not o.get('font'):
            o['font'] = assets.get('regular', 'C:/Windows/Fonts/arial.ttf')
        for key in ('image', 'video', 'font'):
            if o.get(key):
                a = assets.get(o[key], o[key])
                if isinstance(a, dict):  # an asset with defaults, e.g. {"file": ..., "crop": "940:360:180:180"}
                    for k, v in a.items():
                        if k != 'file':
                            o.setdefault(k, v)
                    a = a['file']
                o[key] = resolve(a)
    if plan.get('captions', {}).get('file'):
        plan['captions']['file'] = resolve(plan['captions']['file'])
    grade = plan.get('grade', b.get('grade', 'none'))
    plan.update(_path=str(plan_path), _base=str(base), _brand=b, _bpm=bpm, _total=bounds[-1] / fps,
                _frames=bounds[-1], _cw=cw, _ch=ch, _fps=fps,
                _grade=GRADES.get(grade, grade), _safe=safe_zone(cw, ch, plan.get('safe', preset.get('safe'))), _dest=preset)
    return plan


def when(ref, plan):
    """A time reference: a number, 'end', 'shot3.start', 'shot8.start+1.7', 'end-0.6'."""
    if ref is None:
        return plan['_total']
    if isinstance(ref, (int, float)):
        return float(ref)
    m = re.fullmatch(r'\s*(end|shot(\d+)\.(start|end))\s*([+-]\s*[\d.]+)?\s*', str(ref))
    if not m:
        raise PlanError(f'Cannot read time {ref!r}.')
    if m.group(1) == 'end':
        t = plan['_total']
    else:
        n = int(m.group(2))
        if not 1 <= n <= len(plan['shots']):
            raise PlanError(f'{ref!r}: there is no shot {n}.')
        t = plan['shots'][n - 1][m.group(3)]
    return t + (float(m.group(4).replace(' ', '')) if m.group(4) else 0.0)


def window(info, cw, ch):
    """Crop size in source pixels that fills the canvas at full height or width."""
    w, h = info['width'], info['height']
    if w / h > cw / ch:
        return int(round(h * cw / ch / 2) * 2), h
    return w, int(round(w * ch / cw / 2) * 2)


def crop_xy(info, cw, ch, cx=0.5, cy=0.5):
    ww, wh = window(info, cw, ch)
    x = min(max(0, round(cx * info['width'] - ww / 2)), info['width'] - ww)
    y = min(max(0, round(cy * info['height'] - wh / 2)), info['height'] - wh)
    return ww, wh, x, y


def picture_box(s, plan):
    """The framed picture area of a shot, or None when it fills the canvas.

    Plan-level "picture" applies to every shot; a shot's own "picture" overrides it, and "full" makes it fill the canvas.
    """
    p = s.get('picture', plan.get('picture'))
    if not p or p == 'full':
        return None
    cw, ch = plan['_cw'], plan['_ch']
    w, h = (int(v) // 2 * 2 for v in p['size'])
    x = (cw - w) // 2 if p.get('x', 'center') == 'center' else int(p['x'])
    y = (ch - h) // 2 if p.get('y', 'center') == 'center' else int(p['y'])
    return {'w': w, 'h': h, 'x': x, 'y': y, 'bg': p.get('background', 'black')}


def target(s, plan):
    """Pixel size a shot's picture is cropped and scaled to."""
    box = picture_box(s, plan)
    return (box['w'], box['h']) if box else (plan['_cw'], plan['_ch'])
