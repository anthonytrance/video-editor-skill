# Craft rules for every edit

These hold whatever the spine. They come from the 2026-11 Hengelo afterparty reel, Meta's Reels guidance and the critiques that improved it.

## Opening

The first second decides whether people stay. Open on the strongest recognisable moment that also says who and where: a face, a peak gesture, the crowd at full energy. No slow fades in, no logo on black, no establishing shot that needs context. Put the who and where as text in the first shot, gone by the first cut.

## Shot choice

Every shot shows a different moment. The checker blocks reused footage, but variety also means different subjects, angles and distances: wide crowd, close face, hands on the decks, a reaction, a detail. Three side profiles of the same person in a row read as one shot, even from three different clips. Alternate the people. Prefer sharp, well-lit moments; a soft shot is fine only at peak energy where motion carries it. Look for blockers before choosing: hands over faces, phones held up in frame, heads cut by the crop, a flash that whites out the frame.

## Framing for vertical

A 9:16 window from 16:9 footage is about a third of the width. Put the subject's face or the action at roughly a third from the top or centre, never cut heads, and keep the subject out of the bottom third where captions and the app UI sit. Two people far apart don't fit: choose one, or `pan` from one to the other over 2 bars. Never pad with black bars or a blurred box (the `fit` move) unless the owner asks. A framed picture on a designed background is a different thing, chosen deliberately (see formats.md). Reels are previewed in the feed through a central 4:5 window and on the grid through a 3:4 one, so the hook and the key text must read in the centre.

## Pace

Music spine: 1 to 3 bars per shot, faster into the drop, a punch on the drop, a longer hold for the closer. Speech spine: cut where the speaker breathes or ends a phrase, never mid-word; Pictures laid over a running voice (a `sound` item) start and end on phrase boundaries too, and show what is being said at that moment. Story spine: cut on action (a step, a turn, a door) and give each place a beat to land. Mix lengths; a uniform rhythm feels mechanical.

## Ending

Land the arc: the last shot is a resolution (applause, a hug, a wave, the empty room, the view home), held long enough for the end text. Dim it to about 50% before the text so the words read. End text is short and warm, in the brand's style. Fade the audio out over the last half second rather than cutting it.

## Safe zones

On vertical video the app covers about the top 14% (account name, close button), the bottom 35% (caption, music line, comment box) and a strip on the right (buttons). On 1080x1920 that leaves text between y 269 and y 1248, with about 65 px side margins. The checker measures every text line with the real font. Logos may sit higher if they're decorative, and the checker only warns for them.

## Text

Short uppercase lines, two at most at a time, white with a soft shadow, in the brand fonts. Headline 56 to 66 px bold, detail 44 to 50 px regular. Each line stays on screen at least 1.5 seconds per 4 words. No em-dashes; use a middle dot or spacing in dates and lists ("HENGELO  ·  07.11.2026"). Write names exactly as the owner spells them, and confirm spellings from transcripts or voice notes rather than guessing.

## Colour

One grade for the whole edit keeps different cameras together. `club` deepens blacks, lifts saturation and adds a slight warmth and vignette for dark venues; `natural` is gentle for daylight, travel and talking heads. Fix single outliers with a shot `extra` (`warm`, `cool`, `lift`) rather than a new grade. Don't chase per-shot matching beyond that unless a shot visibly jumps.

## Sound

Music edits: start the track on a downbeat, ideally a few bars before a drop, and cut with the grid. Speech: keep the voice at 0 dB, music ducked under it by the sidechain (on by default), and a short fade on each speech shot. Crowd peaks (a cheer, a sing-along) can sit on top of the music with `audio_db` around -6. Don't loudness-normalise a mastered DJ mix, but never deliver it at full scale either: the default headroom exists because the first reel went out peaking 0.9 dB over full scale after AAC encoding. Use `loudnorm` -14 when voices or ambience carry the edit. Phone voices are often far quieter than a master: measure before mixing (`ffmpeg -i clip.mp4 -af ebur128 -f null -` prints the loudness) and raise `audio_db` or `db` until the voice is clearly above the music. A starting point, not a platform rule: voice around -16 LUFS on its own, music 12 to 18 dB under it while someone speaks. Crowd and ambience go on top with `"duck": false`.

## Size and delivery

30 seconds of 1080x1920 at CRF 18 is about 45 MB. Raise `crf` to 20 or 21 if it must stay under a 50 MB upload limit. Delivered files are never overwritten: new version, new name.

## Verification habits

Read every contact sheet yourself. Treat Gemini's notes as leads, and check timecodes against the plan before acting: it misreads safe text placement and invents typos. Describe the finished edit to the owner in words, shot by shot.
