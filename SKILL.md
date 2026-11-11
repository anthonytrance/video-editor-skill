---
name: video-editor
description: "Edit short videos from raw footage with FFmpeg: afterparty and gig reels, shout-outs, talking clips mixed with gig footage, travel or vlog stories, and any hybrid. A JSON edit plan drives frame-exact cuts, 16:9 to 9:16 reframing, moves, grade, text, logos, music, ducked speech and voice over other pictures; a checker blocks reused footage, letterboxing and text under the app UI; knows each destination (Reel, Story, carousel, feed, TikTok, Shorts, YouTube) and designs like a framed square inside a 9:16 Reel; Gemini logs footage and critiques renders. Use for any multi-shot edit, recut or 'make a reel, aftermovie or clip from this footage'."
---

# Video editor

Turns a folder of clips into a finished short video. The agent is the editor: it decides the story and writes an edit plan, and the scripts do the mechanical parts exactly, so cuts land on the beat, nothing repeats by accident and nothing gets letterboxed.

Read [LOCAL.md](LOCAL.md) first if it exists: it holds this machine's Python, brand file and media folders. The owner, brand fonts, logos and default look live in a brand file (`~/.video-editor/brand.json`, see [references/brand.md](references/brand.md)), never in the scripts.

Single clips that only need trimming or a simple crop, captions on one clip, and publishing belong to the social skill of the installation (for XNP: `xnp-social`). This skill makes the edit; that skill reviews, captions, plans and publishes it.

## There is no list of video types

Every request is a mix. Don't look for a matching template. Instead decide four things from the brief, per section if the video changes character halfway:

1. **The spine: what drives the timing.**
   Music: cuts on bars and beats, shots chosen for energy, the drop is the peak (`len` in `"2bar"`, `"1beat"`).
   Speech: the words set the length, picture cuts at phrase ends, music ducks under the voice (`audio_db` on the talking shot, lengths in seconds).
   Story or chronology: arrival, build, moment, afterglow; cut on action and place changes, music is a bed.
   A hybrid switches spine per section: a 6 second shout-out on speech, then gig footage on the beat; or a travel story on chronology with a beat-cut montage at the gig.
2. **Destination and design.** Where it goes (Reel, Story, carousel, feed, TikTok, Shorts, YouTube) and how to use that space: full bleed, a framed square or 4:5 picture on a designed background, or both switching per shot. Choose from the footage and the purpose, not by habit; a wide moment that a 9:16 crop would ruin may want a framed Reel, a carousel or a 16:9 recap. Read [references/formats.md](references/formats.md) for what each platform does with the picture and when each design fits. Length follows the destination and the material.
3. **Must-haves.** Named people who must appear and be recognisable, a logo, a date, a thank-you, a specific moment, a caption line. Ask only if the brief truly leaves one open.
4. **Sound layers.** Music only; music plus crowd or ambience peeks; speech with music under it; speech only. Speech gets captions (see Captions below).

Then write the plan, with `"destination"` set so the canvas, safe area and length limit follow. [references/examples.md](references/examples.md) shows four worked briefs (afterparty reel, shout-out, shout-out into gig footage, travel story) as reasoning, not as types to copy. [references/craft.md](references/craft.md) has the editing rules that apply to all of them.

## Workflow

Scripts are in `scripts/`; run them with the Python from LOCAL.md, `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`, FFmpeg and ffprobe on PATH. Work in a project folder outside the skill (`src/`, `audio/`, `log/`, `proxy/`, `out/`, `review/`, `edit.json`).

1. **Brief, before any cutting.** Write `brief.txt` in the project folder; the checker flags a plan without one and Gemini reads it. It must answer: what the video is for in one sentence (a thank-you after a night, a track promo and an announcement are three different edits of the same footage); the destination; who is in the footage, how to tell them apart (age, hair, clothes, where they stand) and who must be seen; which track and which part of it (say whether the part has a drop, a build or only a breakdown); the must-haves, with names and dates spelled exactly; the length; and whether speed or polish matters more. Take what the request and earlier briefs already say, then ask the owner for everything still open in one message and wait for the answer before the first render. Never guess who a person is, what the video is for or which part of the music is meant: each of those guesses cost a full round on the first reel. The owner may not be able to see the footage, so ask in terms they can answer ("the older man in the black shirt on the left, is that Richard?"). Logging the footage (step 2) can run while waiting. Keep a `notes.md` next to it: the owner's feedback in their words, decisions and why, and what each delivered version was. A long job outlives the conversation's memory; the folder must hold everything needed to continue.
2. **Log the footage.** `gemini.py log WORKDIR src/*.mp4 --context brief.txt --ratio 9:16` writes `log/NAME.json` per clip: moments with who is where (x as a fraction for cropping), action, emotion, energy, sound, speech, quality, whether a 9:16 window holds the subjects, the best crop centre and a use (opener, peak, reaction...). About one US cent per clip. Logs are leads: confirm faces, crop centres and "best moments" on frames before building on them.
3. **Look.** `sheet.py` makes labelled contact sheets in one FFmpeg run: `--every 2` through a clip, `--times`, candidate comparison with `a.mp4@3 b.mp4@10.5`, `--crop 9:16 --cx 0.4` to see a source as it will be framed, `--grid 10` for crop planning. Read the image yourself; never ask the owner to look.
4. **Plan.** Write `edit.json` ([references/edit-format.md](references/edit-format.md)). Each shot names a different moment; give each a note saying why it is there.
5. **Check.** `validate.py edit.json` (render.py also runs it and refuses on errors). Errors: the same footage used twice, a source too short, unknown move, boxed `fit` without permission, text in the platform UI zones, missing files, music too short. Warnings: shots from the same clip less than 2s apart, look-alike shots, off-beat cuts, black edges inside the framed source, logos near the UI zones. Read every warning and decide; don't just silence it.
6. **Draft render.** `render.py edit.json --out out/v1-draft.mp4 --draft` (half size, fast). Then `sheet.py out/v1-draft.mp4 --plan edit.json --out review/v1.png` shows the start, middle and end of every shot: check framing, heads, text placement and that each shot is what the note says.
7. **Full render.** `render.py edit.json --out out/v1.mp4`. Slow preset, about 5 minutes for 30 seconds of 4K sources; render.py then checks size, length, sound, black bars per shot, black frames and the plan's `max_mb`.
8. **Critique.** `gemini.py review out/v1.mp4 --context brief.txt --plan edit.json --out review/v1.json` (under one cent). Treat each note as a claim: check it against frames or the plan before changing anything. It has called correct text "unsafe" and a correct date "a typo". Its real catches were repeated-looking shots, a hand blocking a key gesture, a phone in frame, a flash that read as a glitch.
9. **Iterate** with new version numbers; never overwrite a delivered file. Keep `edit.json` per version (copy to `edit-v2.json`) so any version can be re-rendered.
10. **Deliver with the report, every time.** Run `report.py edit.json out/v1.mp4` and send its output with the file, unasked: size and length, destination and design, whether colour correction was applied and which, the music section, loudness and peak, every shot with its time and note, every text with its times, and what the checker still warns about. Add in your own words what you saw on the contact sheet, what changed since the last version, and what a sighted person should still confirm; the report's last line lists what no machine checked. If the file is over the delivery limit in LOCAL.md, say so and use the other route before the owner has to ask. Then hand the file to the social skill for review, captions and publishing. Publishing always needs the owner's explicit approval, and anything going public deserves one look by a sighted person first.

## Captions

Speech captions are the social skill's job: render the edit first, then run its captions helper (for XNP: `xnp-social/scripts/captions.py transcribe` on the finished render, so the word times match the edit), follow its mandatory approval step, then burn. If an approved `.srt` or `.ass` already exists for the final timeline, the plan's `captions.file` burns it during render instead.

## Honest limits

As of 2026-11 one real edit has been made with this skill: a music-driven afterparty reel. Speech, voice over other pictures, phone HDR footage, carousels and 16:9 pass synthetic tests of the mechanics but have not been through a real edit and a human's eyes. On the first real one of each, go slower, check more frames, and write what you learn back into the references.

The look-alike check is a picture hash plus mean colour: it catches the same moment twice, not "the same person from the same angle" in different moments. That semantic check comes from the Gemini logs and review and from reading the contact sheet. There is no automatic beat detection: give the BPM and a start point on a downbeat (`music.start`), then the grid is exact. There is no face tracking: pans and crop centres come from the logs and sheets. Gemini's timecodes can drift on long clips; the proxies carry a burned-in timecode to keep them honest, and `log` warns when moments run past the clip.

## Files

`scripts/common.py` plan loader, timing maths, probe, brand, grades. `scripts/render.py` the one-pass renderer. `scripts/validate.py` the checker. `scripts/sheet.py` contact sheets. `scripts/gemini.py` logging and review. `scripts/report.py` the delivery report. References: [formats.md](references/formats.md), [edit-format.md](references/edit-format.md), [craft.md](references/craft.md), [examples.md](references/examples.md), [brand.md](references/brand.md).
