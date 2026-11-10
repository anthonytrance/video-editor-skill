# The edit plan (edit.json)

One JSON file describes the whole edit. Relative paths resolve from the plan's folder. Only `shots` is required.

```json
{
  "title": "what this is",
  "canvas": [1080, 1920],
  "fps": 24,
  "duration": 31.375,
  "grade": "club",
  "music": {"file": "audio/track.wav", "start": 216.0, "bpm": 140, "gain_db": 0, "duck": true, "duck_ratio": 8},
  "fade_out": 0.6,
  "loudnorm": null,
  "max_mb": 50,
  "shots": [ ... ],
  "overlays": [ ... ],
  "captions": {"file": "captions.ass"}
}
```

## Top level

`canvas` [width, height], default 1080x1920. `fps` default 24 (match the footage's cadence feel; 25 or 30 are fine). `duration` is the total length, needed when a shot uses `"len": "rest"`; it accepts the same units as shot lengths. `grade` names a look from `common.GRADES` (`club`, `natural`, `none`) or is a raw FFmpeg filter chain; default from the brand file. `fade_out` is the audio fade at the end in seconds. `loudnorm` is a target LUFS such as -14, off by default: don't normalise a DJ mix that is already mastered. `max_mb` warns when the render is bigger (Telegram bots take 50 MB). `brand` overrides the brand file path. `safe` overrides the UI-safe area as fractions or pixels: `{"top": 0.14, "bottom": 0.35, "side": 0.06}` is the vertical default. `allow_fit: true` permits the boxed `fit` move. `min_gap` (seconds, default 2) sets when two shots from one clip count as too close. `cut_on_beat: false` silences the off-beat warnings on speech or story spines. `crf` sets quality, default 18.

## music

`file`, `start` (seconds into the track; put it on a downbeat so the bar grid is true), `bpm` (makes `"2bar"` and `"1beat"` lengths work and enables the off-beat check), `gain_db`, `duck` (default true: the music dips under any shot sound), `duck_ratio`. No music is fine: speech-only or ambience-only edits just use shot sound.

## shots

Played in order, back to back. Each:

```json
{"src": "src/P1590406.mp4", "in": 10.0, "len": "2bar",
 "frame": {"move": "pan", "cx": [0.38, 0.74]},
 "speed": 1.0, "audio_db": null, "extra": "warm", "grade": null,
 "note": "hook: Richard's back to Pitch, both arms up"}
```

`in` is the source time in seconds. `len` is a number of seconds or a string: `"2bar"`, `"3beat"`, `"1.5s"`, `"36f"` (frames), or `"rest"` for the remainder of `duration` (last shot only in practice). Boundaries are rounded to whole frames from the running total, so a run of bars never drifts.

`frame.move`:
`still` holds the crop. `push` zooms in slowly (to `zoom`, default 1.06). `pull` the reverse. `punch` jumps to `zoom` 1.12 and settles over `decay` 0.4s: use it on a drop. `pan` slides from the first to the second `cx` (and/or `cy`) with ease in and out. `fit` shows the whole frame boxed on a blurred copy of itself; it mixes aspect ratios, so the checker refuses it unless `allow_fit` is set.

`cx` and `cy` are the crop centre as fractions of the source (0 left or top, 1 right or bottom). A 16:9 4K source cropped to 9:16 keeps a window about 30% of its width, so cx matters; take it from the Gemini log's `crop_center` or a `sheet.py --crop 9:16 --grid 10` sheet.

`speed` below 1 is slow motion (setpts; frames are repeated, so sources at 50/60 fps look best). `audio_db` puts the shot's own sound on the speech bus at that gain (0 is as recorded); null or absent mutes it. Sound follows speed only between 0.5 and 2. `afade` (default 0.03) softens the edges of shot sound. `extra` adds `warm`, `cool` or `lift` (or a raw filter, or a list) before the grade. `grade` per shot overrides the plan's grade, for example `"natural"` on a daylight shot inside a club edit. `note` is for people and for Gemini's review prompt.

## overlays

Drawn in list order over the finished picture; text is always drawn last, on top. Times `t: [from, to]` accept seconds, `"end"`, `"shotN.start"`, `"shotN.end"`, with `+` or `-` offsets (`"shot8.start+1.7"`); `null` as the end means the end of the edit. `fade` is the fade-in, `fade_out` the fade-out (default 0.1, skipped when it runs to the end).

Text: `{"text": "B2B WITH RICHARD DURAND", "font": "bold", "size": 58, "y": 650, "t": [0.35, "shot1.end"]}`. `font` is a brand asset name or a font file; default the brand's `regular`. `x` is `"center"` (default) or pixels. Optional `color`, `shadow` (default true), `box` (a colour like `"black@0.5"`) and `pad`. Text in the UI zones is an error; `safe_ok: true` overrides when the owner wants it anyway.

Image or video (logo, sticker, animated title): `{"video": "cd-logo", "ss": 0, "width": 860, "y": 300, "t": [0, "shot1.end"]}`. `image` for stills. A brand asset name pulls the file and its defaults (such as `crop`) from the brand file. `ss` starts an animated asset at that second (use a later `ss` to show the settled state of a logo animation). `width` in canvas pixels, `x` `"center"` or pixels, `y` pixels from the top. Needs an alpha channel to float over the picture (ProRes 4444, PNG, WebM VP9 with alpha).

Dim: `{"dim": 0.5, "t": ["shot8.start+1.7", null], "fade": 0.6}` lays black at that opacity over everything drawn before it, to make room for end text.

## captions

`{"file": "subs.ass"}` burns an approved subtitle file timed to the final edit. Normally captions are made after the render with the social skill's helper instead; see SKILL.md.

## Times and the grid

At 140 BPM one beat is 0.4286s and one bar 1.7143s (41.14 frames at 24 fps). Common shot lengths: 1 bar for quick hits, 2 bars as the default, 3 to 4 bars for a hold or the money shot. Put the drop on a shot boundary: if the drop is 8 bars after `music.start`, the shots before it must add up to 8 bars.
