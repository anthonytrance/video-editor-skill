# Worked briefs

Four briefs reasoned through with the four decisions from SKILL.md. They show how to think, not templates: real requests will mix these, and new ones will look like none of them.

Only the first has been made for real (2026-11). The other three are reasoning whose mechanics pass synthetic tests but which no real edit and no human eye has confirmed yet. Expect to adjust them, and rewrite the paragraph when the first real one is done.

## Afterparty reel (music spine), made for real

Brief: 30 seconds for Reels from a night where the owner played back to back with a headliner, using the owner's own track, logo and a thank-you at the end. Footage: eight 4K 16:9 clips from a photographer, crowd and booth.

Spine: music all the way. 140 BPM, started on a downbeat 4 bars before a drop at 216s, so shots 1 and 2 add up to the build and the drop lands on the cut into shot 2 with a `punch`. Destination and design: Reel, 1080x1920, full bleed, 24 fps like the footage, about 31 seconds. Must-haves: both DJs recognisable early, the label logo, "B2B WITH RICHARD DURAND", place and date, end thank-you. Sound: music only; the camera audio is muted.

Shape: hook shot pans from the headliner to the owner with the logo and text over it; then the drop on a crowd-POV of both; then alternating owner energy, a dancer, CO2 over the crowd, high-fives; closer is the owner clapping overhead, dimmed, with the logo and "THANK YOU FOR / CHASING DREAMS WITH US". The plan is in the project folder of that event (see LOCAL.md).

What went wrong on the way, so it doesn't again: the first cut used a breakdown with no drop because nobody checked what the chosen part of the track was; the second was built as a promo for the track when the purpose was a thank-you for the night; the headliner was not identified until the owner said who the older man was; repeated footage and a boxed shot reached human reviewers; and it went out peaking above full scale. The brief step, the checker and the headroom default each exist because of one of these.

## Shout-out (speech spine)

Brief: a 12 second selfie video of a festival host saying hello to the owner's fans, to post before the gig.

Expect phone footage: usually vertical already, 30 fps, often HDR, voice much quieter than a music master. So set `"fps": 30`, let the renderer convert the HDR and compare its colour with a frame of the original on a sheet, and measure the voice before mixing (craft.md, Sound).

Spine: speech. The words decide the length: keep a breath before the first word and after the last, nothing more. A vertical clip fills the canvas, so the framing work is small: one shot with a slow `push`, or two shots split at a phrase break, tighter on the second. A landscape clip is cropped around the face (`cx` from the log). Must-haves: the speaker's face clear of text, the event name and date as text placed away from the face (the log says where the face sits). Sound: the voice on top, the owner's track 12 to 18 dB under it and ducked, `"loudnorm": -14` because the voice carries the edit, `cut_on_beat: false`.

The music cannot swell while the person is still on screen talking: the duck only lets go when the voice stops. For a lift at the end, add a closing shot with no voice, 1 to 2 seconds of logo or gig picture, and the music rises into it by itself (the duck releases in under half a second). Captions via the social skill after render, approved before burn; a talking video without captions is unfinished.

## Shout-out into gig footage (hybrid: speech, then music)

Brief: an artist's 8 second "can't wait to see you Saturday" clip, followed by highlights of the owner's last set there.

Two ways to join them, and the second is usually the stronger video.

Hard handover: the artist talks to camera for the whole sentence, then the gig section starts. Give the music a `sync` so a downbeat, ideally a drop, lands exactly on the cut out of the speech: `"sync": {"track": 216.0, "at": "shot2.start"}`. The speech can be any length; nothing has to be trimmed to fit the beat, and the bar lengths after the cut are exact.

Voice over pictures: show the artist for the first few words so people see who is speaking, then cut to the gig while the voice continues, so "can't wait to see you Saturday" plays over the crowd they will see. Put the whole sentence in a `sound` item and mute the talking shot; give the item the shot's `in` and the shot's start so the lips match. Cut the pictures under the voice on phrase ends and on what is being said, not on the beat. When the voice ends the music comes up by itself; use `sync` to put a downbeat on the first cut after the last word, and go to bars from there.

In both, a `punch` on the first music cut marks the change of gear. Captions cover the speech only; the transcriber finds nothing in the music part.

## Travel story (story spine, beat-cut montage inside)

Brief: 45 to 60 seconds of a weekend trip to a gig abroad: train, hotel, soundcheck, the set, the morning after. Phone clips in mixed orientation, some with the owner talking to camera.

Spine: chronology. Each place gets its own short section and lands for a moment before moving on; travel shots run 1.5 to 3 seconds and cut on movement. Destination and design: a 9:16 Reel at the footage's own frame rate (phones: 30). Vertical clips fill the canvas; landscape ones are cropped with the `cx` from the logs, or shown framed when the view is the point (a skyline, a stage) rather than cropped to a sliver. Grade: `natural` for the plan and `"grade": "club"` on the gig shots; HDR clips are converted, so check that one phone's clips don't look different from another's.

Sound is what makes this kind feel alive, and it has three layers. A song as the bed. The owner's voice: a talking clip can be a shot with `audio_db`, but better, start on the face and let the voice run on as a `sound` item over the next two or three travel shots. And the places themselves: train, street, soundcheck, at `audio_db` around -12 with `"duck": false` so they sit on the music without making it pump; the same for a crowd cheer in the set. Use `"loudnorm": -14`.

Inside the gig section switch to the beat for a 4 to 8 bar montage; a second `sync` is not possible (one music file, one start), so choose the music start so the montage's first cut is on a downbeat, or accept free cuts before it and exact bars after. Must-haves: place names as small text when each section starts. A minute of 20 to 25 shots renders slowly: settle the cut on drafts first. Captions for the talking parts after render.

## What carries across

Whatever the brief: nothing is cut before the brief is answered, the spine sets lengths and where cuts may fall, every shot is a different moment with a note saying why, the hook is in the first second, text stays in the safe area, the ending resolves, the review loop (contact sheet, Gemini, verify, fix) runs before anything goes to the owner, and every delivery carries the report.
