"""Offline tests: tiny synthetic clips, no network. Run with pytest from this folder."""
import json
import subprocess

import pytest

from common import PlanError, binary, load, seconds, when
import render
import validate


@pytest.fixture(scope='module')
def work(tmp_path_factory):
    d = tmp_path_factory.mktemp('ve')
    ff = binary('ffmpeg')
    for name, src in (('a', 'testsrc2'), ('b', 'smptebars')):
        subprocess.run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', f'{src}=s=640x360:r=24:d=8',
                        '-f', 'lavfi', '-i', 'sine=f=440:d=8', '-shortest', '-c:v', 'libx264', '-c:a', 'aac',
                        str(d / f'{name}.mp4')], check=True)
    subprocess.run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=220:d=20', str(d / 'music.wav')], check=True)
    return d


def plan(work, name='edit.json', **over):
    p = {'canvas': [360, 640], 'fps': 24, 'brand': str(work / 'no-brand.json'),
         'music': {'file': 'music.wav', 'start': 0, 'bpm': 120},
         'shots': [{'src': 'a.mp4', 'in': 0, 'len': '2bar', 'frame': {'move': 'push', 'cx': 0.4}},
                   {'src': 'b.mp4', 'in': 1, 'len': '1bar', 'frame': {'move': 'pan', 'cx': [0.3, 0.7]}},
                   {'src': 'a.mp4', 'in': 5, 'len': 'rest', 'frame': {'move': 'punch'}, 'audio_db': -6}],
         'duration': '4bar',
         'overlays': [{'text': 'HELLO', 'size': 30, 'y': 200, 't': [0, 'shot1.end']},
                      {'dim': 0.5, 't': ['shot3.start+0.5', None]}]}
    p.update(over)
    p = {k: v for k, v in p.items() if v is not None}
    path = work / name
    path.write_text(json.dumps(p), encoding='utf-8')
    return path


def test_units():
    assert seconds('2bar', 120, 24) == 4.0
    assert seconds('3beat', 120, 24) == 1.5
    assert seconds('36f', None, 24) == 1.5
    with pytest.raises(PlanError):
        seconds('2bar', None, 24)


def test_timing_is_frame_exact(work):
    p = load(plan(work))
    assert [s['f0'] for s in p['shots']] == [0, 96, 144]
    assert p['_frames'] == 192
    assert when('shot3.start+0.5', p) == pytest.approx(6.5)
    assert when(None, p) == 8.0


def test_good_plan_passes(work):
    errors, _ = validate.check(load(plan(work)), looks=False, bars=False)
    assert errors == []


def test_checker_catches_mistakes(work):
    shots = [{'src': 'a.mp4', 'in': 0, 'len': 3},
             {'src': 'a.mp4', 'in': 2, 'len': 2, 'frame': {'move': 'fit'}},
             {'src': 'b.mp4', 'in': 7, 'len': 2}]
    over = [{'text': 'LOW TEXT', 'size': 30, 'y': 600}]
    errors, _ = validate.check(load(plan(work, 'bad.json', shots=shots, duration=7, overlays=over)),
                               looks=False, bars=False)
    text = ' '.join(errors)
    assert 'reuse the same footage' in text
    assert '"fit"' in text
    assert 'b.mp4 is' in text
    assert 'LOW TEXT' in text


def test_draft_render(work):
    p = load(plan(work))
    out = work / 'draft.mp4'
    subprocess.run(render.build(p, out, draft=True), check=True)
    from common import probe
    info = probe(out)
    assert (info['width'], info['height']) == (180, 320)
    assert abs(info['duration'] - 8.0) < 0.1 and info['audio']


def test_destination_presets(work):
    p = load(plan(work, 'dest.json', destination='carousel', canvas=None))
    assert (p['_cw'], p['_ch']) == (1080, 1350)
    assert p['_safe']['bottom'] == round(0.04 * 1350)
    errors, _ = validate.check(load(plan(work, 'story.json', destination='story', duration=70,
                                         shots=[{'src': 'a.mp4', 'in': 0, 'len': 'rest'}])), looks=False, bars=False)
    assert any('at most 60s' in e for e in errors)
    _, warnings = validate.check(load(plan(work, 'sq.json', destination='reel', canvas=[360, 360])),
                                 looks=False, bars=False)
    assert any('blank space' in w for w in warnings)


def test_framed_picture_render(work):
    shots = [{'src': 'a.mp4', 'in': 0, 'len': '2bar', 'picture': 'full'},
             {'src': 'b.mp4', 'in': 1, 'len': '1bar', 'frame': {'move': 'pan', 'cx': [0.3, 0.7]}},
             {'src': 'a.mp4', 'in': 5, 'len': 'rest', 'frame': {'move': 'punch'},
              'picture': {'size': [360, 360], 'y': 100, 'background': 'blur'}}]
    path = plan(work, 'framed.json', shots=shots, picture={'size': [360, 360], 'background': '#202020'})
    p = load(path)
    errors, _ = validate.check(p, looks=True, bars=False)
    assert errors == []
    out = work / 'framed.mp4'
    subprocess.run(render.build(p, out), check=True)
    from common import probe
    assert (probe(out)['width'], probe(out)['height']) == (360, 640)
    errs, warns = validate.check_render(p, out)
    assert errs == [] and not any('black bars' in w for w in warns)
