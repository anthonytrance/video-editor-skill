"""Offline tests: tiny synthetic clips, no network. Run with pytest from this folder."""
import json
import os
import subprocess
import zipfile

import pytest

from common import PlanError, binary, load, seconds, when
import cleanup
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


# ---------- sound: buses, ducking, headroom, sync ----------

def band_db(path, freq, t0, dur):
    """Mean level of one tone in a stretch of a file."""
    import re
    r = subprocess.run([binary('ffmpeg'), '-hide_banner', '-nostats', '-ss', str(t0), '-t', str(dur), '-i', str(path), '-vn',
                        '-af', f'bandpass=f={freq}:t=h:w=40,volumedetect', '-f', 'null', '-'],
                       capture_output=True, text=True, errors='replace')
    return float(re.search(r'mean_volume: (-?[\d.]+) dB', r.stderr).group(1))


def silent_shots():
    return [{'src': 'a.mp4', 'in': 0, 'len': 2}, {'src': 'b.mp4', 'in': 0, 'len': 2}, {'src': 'a.mp4', 'in': 4, 'len': 2}]


def test_voice_over_other_pictures_ducks_music(work):
    # The voice of a.mp4 (440 Hz) runs from 2s to 4s, under the pictures of b.mp4; the music (220 Hz) dips there.
    path = plan(work, 'vo.json', shots=silent_shots(), duration=None, overlays=[],
                music={'file': 'music.wav', 'start': 0},
                sound=[{'src': 'a.mp4', 'in': 1, 'len': 2, 'at': 'shot2.start', 'db': 12}])
    p = load(path)
    assert validate.check(p, looks=False, bars=False)[0] == []
    out = work / 'vo.mp4'
    subprocess.run(render.build(p, out, draft=True), check=True)
    assert band_db(out, 440, 2.3, 1.4) > band_db(out, 440, 0.2, 1.4) + 20      # voice only where placed
    assert band_db(out, 220, 2.5, 1.2) < band_db(out, 220, 0.2, 1.4) - 3       # music dips under it


def test_ambience_does_not_duck_music(work):
    path = plan(work, 'amb.json', shots=silent_shots(), duration=None, overlays=[],
                music={'file': 'music.wav', 'start': 0},
                sound=[{'src': 'a.mp4', 'in': 1, 'len': 2, 'at': 2, 'db': 12, 'duck': False}])
    p = load(path)
    out = work / 'amb.mp4'
    subprocess.run(render.build(p, out, draft=True), check=True)
    assert band_db(out, 440, 2.3, 1.4) > band_db(out, 440, 0.2, 1.4) + 20
    assert abs(band_db(out, 220, 2.5, 1.2) - band_db(out, 220, 0.2, 1.4)) < 1.5


def test_sound_outside_the_edit_is_an_error(work):
    p = load(plan(work, 'late.json', shots=silent_shots(), duration=None, overlays=[],
                  sound=[{'src': 'a.mp4', 'in': 0, 'len': 3, 'at': 5}]))
    assert any('outside' in e for e in validate.check(p, looks=False, bars=False)[0])


def test_full_scale_master_gets_headroom(work):
    ff = binary('ffmpeg')
    subprocess.run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=f=220:d=20', '-af', 'volume=18dB',
                    str(work / 'loud.wav')], check=True)
    p = load(plan(work, 'loud.json', shots=silent_shots(), duration=None, overlays=[], music={'file': 'loud.wav', 'start': 0}))
    out = work / 'loud.mp4'
    subprocess.run(render.build(p, out), check=True)
    lufs, peak = validate.loudness(out)
    assert peak is not None and peak <= -1.0
    assert not any('peaks at' in w for w in validate.check_render(p, out)[1])


def test_music_sync_moves_the_grid(work):
    # Speech for 2.3s, then the music section: track time 6.0 (a downbeat) must fall on the cut into shot 2.
    shots = [{'src': 'a.mp4', 'in': 0, 'len': 2.3, 'audio_db': 0},
             {'src': 'b.mp4', 'in': 0, 'len': '1bar'}, {'src': 'a.mp4', 'in': 4, 'len': '1bar'}]
    p = load(plan(work, 'sync.json', shots=shots, duration=None, overlays=[],
                  music={'file': 'music.wav', 'bpm': 120, 'sync': {'track': 6.0, 'at': 'shot2.start'}}))
    assert abs(p['music']['start'] - (6.0 - p['shots'][1]['start'])) < 1e-9
    errors, warnings = validate.check(p, looks=False, bars=False)
    assert errors == [] and not any('off the beat' in w for w in warnings)
    early = load(plan(work, 'sync2.json', shots=shots, duration=None, overlays=[],
                      music={'file': 'music.wav', 'bpm': 120, 'sync': {'track': 1.0, 'at': 'shot2.start'}}))
    assert any('before the track begins' in e for e in validate.check(early, looks=False, bars=False)[0])


# ---------- phone footage: HDR and frame rate ----------

def test_hdr_and_odd_frame_rate_sources(work):
    ff = binary('ffmpeg')
    made = subprocess.run([ff, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=640x360:r=30:d=6',
                           '-f', 'lavfi', '-i', 'sine=f=440:d=6', '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p10le',
                           '-x264-params', 'colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc',
                           '-c:a', 'aac', str(work / 'hlg.mp4')])
    if made.returncode:
        pytest.skip('this FFmpeg cannot write a 10-bit HLG test clip')
    from common import probe
    assert probe(work / 'hlg.mp4')['hdr'] is True
    shots = [{'src': 'hlg.mp4', 'in': 0, 'len': 2}, {'src': 'a.mp4', 'in': 0, 'len': 2},
             {'src': 'hlg.mp4', 'in': 3, 'len': 2, 'picture': {'size': [360, 360], 'background': 'blur'}}]
    p = load(plan(work, 'hdr.json', shots=shots, duration=None, overlays=[]))
    errors, warnings = validate.check(p, looks=False, bars=False)
    assert errors == []
    assert any('HDR footage' in w for w in warnings) and any('not a multiple' in w for w in warnings)
    out = work / 'hdr.mp4'
    subprocess.run(render.build(p, out, draft=True), check=True)
    assert abs(probe(out)['duration'] - 6.0) < 0.1


# ---------- brief, report, skill header ----------

def test_missing_brief_is_flagged(work):
    p = load(plan(work, 'nobrief.json'))
    assert any('brief.txt' in w for w in validate.check(p, looks=False, bars=False)[1])


def test_delivery_report(work):
    import report
    p = load(plan(work, 'rep.json', title='Test edit', destination='reel'))
    out = work / 'rep.mp4'
    subprocess.run(render.build(p, out), check=True)
    text = report.build(p, out)
    for expected in ('Delivery report: Test edit', 'Destination: reel', 'Colour:', 'Loudness:', 'Shots (3):',
                     '"HELLO" from 0.00s', 'picture dimmed to 50%', 'Not checked by a machine'):
        assert expected in text, expected


def project(tmp_path):
    p = tmp_path / '2026-01-01-night'
    for d in ('src', 'out', 'proxy', 'review', 'log'):
        (p / d).mkdir(parents=True)
    (p / 'edit.json').write_text('{}', encoding='utf-8')
    (p / 'brief.txt').write_text('a thank-you reel', encoding='utf-8')
    (p / 'log' / 'clip.json').write_text('{}', encoding='utf-8')
    (p / 'src' / 'clip.mp4').write_bytes(b'camera original' * 1000)
    (p / 'proxy' / 'clip.mp4').write_bytes(b'proxy')
    (p / 'review' / 'sheet.jpg').write_bytes(b'jpg')
    for i, name in enumerate(('v1.mp4', 'v2.mp4', 'v3.mp4')):
        f = p / 'out' / name
        f.write_bytes(name.encode() * 500)
        os.utime(f, (1_700_000_000 + i, 1_700_000_000 + i))
    return p


def test_cleanup_tidy_keeps_only_the_newest_render(tmp_path):
    p = project(tmp_path)
    assert cleanup.tidy(p, [], confirm=False) == 0
    assert len(list((p / 'out').iterdir())) == 3  # a dry run deletes nothing
    cleanup.tidy(p, [], confirm=True)
    assert [f.name for f in (p / 'out').iterdir()] == ['v3.mp4']
    assert (p / 'src' / 'clip.mp4').exists()


def test_cleanup_close_deletes_only_what_is_proven_stored(tmp_path):
    p = project(tmp_path)
    listing = tmp_path / 'stored.json'
    # nothing proven: big files and keepers stay, only what can be made again goes
    assert cleanup.close(p, [], [], confirm=True) == 1
    assert (p / 'src' / 'clip.mp4').exists() and (p / 'out' / 'v3.mp4').exists() and (p / 'edit.json').exists()
    assert not (p / 'proxy').exists() and not (p / 'out' / 'v1.mp4').exists()
    # footage and render proven, the keepers zip not yet: the keepers stay
    z = p / f'{p.name}-project.zip'
    first = cleanup.content_hash(z)
    names = zipfile.ZipFile(z).namelist()
    assert {'edit.json', 'brief.txt', 'log/clip.json', 'big-files.txt'} <= set(names)
    listing.write_text(json.dumps({'files': [{'content_hash': cleanup.content_hash(p / 'src' / 'clip.mp4')},
                                             {'content_hash': cleanup.content_hash(p / 'out' / 'v3.mp4')}]}))
    assert cleanup.close(p, [], [str(listing)], confirm=True) == 1
    assert not (p / 'src').exists() and (p / 'edit.json').exists() and z.exists()
    # the zip is rebuilt identically, so the hash taken at upload time still proves it
    cleanup.close(p, [], [], confirm=False)
    assert zipfile.ZipFile(z).read('edit.json') == b'{}'
    listing.write_text(json.dumps([{'name': z.name, 'content_hash': cleanup.content_hash(z)}]))
    assert cleanup.close(p, [], [str(listing)], confirm=True) == 0
    assert not p.exists()
    assert first  # hash of the first pack existed before any upload


def test_cleanup_refuses_a_folder_that_is_no_project(tmp_path):
    (tmp_path / 'holiday').mkdir()
    (tmp_path / 'holiday' / 'photo.jpg').write_bytes(b'x')
    with pytest.raises(SystemExit):
        cleanup.check_project(tmp_path / 'holiday')


def test_skill_header_is_valid_yaml():
    yaml = pytest.importorskip('yaml')
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / 'SKILL.md').read_text(encoding='utf-8')
    head = yaml.safe_load(text.split('---')[1])
    assert head['name'] == 'video-editor' and len(head['description']) > 200
