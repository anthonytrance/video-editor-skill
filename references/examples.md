# Worked briefs

Four briefs reasoned through with the four decisions from SKILL.md. They show how to think, not templates: real requests will mix these, and new ones will look like none of them.

## Afterparty reel (music spine)

Brief: 30 seconds for Reels from a night where the owner played back to back with a headliner, using the owner's own track, logo and a thank-you at the end. Footage: eight 4K 16:9 clips from a photographer, crowd and booth.

Spine: music all the way. 140 BPM, started on a downbeat 4 bars before a drop at 216s, so shots 1 and 2 add up to the build and the drop lands on the cut into shot 2 with a `punch`. Format: 1080x1920, 24 fps, about 31 seconds. Must-haves: both DJs recognisable early, the label logo, "B2B WITH RICHARD DURAND", place and date, end thank-you. Sound: music only; the camera audio is muted.

Shape: hook shot pans from the headliner to the owner with the logo and text over it; then the drop on a crowd-POV of both; then alternating owner energy, a dancer, CO2 over the crowd, high-fives; closer is the owner clapping overhead, dimmed, with the logo and "THANK YOU FOR / CHASING DREAMS WITH US". The plan is in the project folder of that event (see LOCAL.md). The review loop fixed three side profiles in a row, a white flash, a hand hiding a rock-on and a phone in frame.

## Shout-out (speech spine)

Brief: a 12 second selfie video of a festival host saying hello to the owner's fans, to post before the gig. Landscape phone video.

Spine: speech. The words decide the length: trim to the first clean word and the last, nothing more. Format: 9:16; the speaker is already centred, so `still` with a slight `push` over the whole clip, or two shots split at a phrase break to switch between a tighter and a wider crop. Must-haves: the speaker's face, the event name and date as text in the top half. Sound: the clip's own voice at `audio_db` 0, the owner's track at -14 dB under it (ducked automatically), music rising for the last second with the logo. `cut_on_beat: false`. Captions via the social skill after render, approved before burn.

## Shout-out into gig footage (hybrid: speech, then music)

Brief: an artist's 8 second "can't wait to see you Saturday" clip, followed by highlights of the owner's last set there.

Spine per section. Section 1 is speech: one or two shots, length in seconds, voice on top, music low. The handover is the hinge: end the speech on a full stop, and start the music section on a downbeat right at that cut (set `music.start` so the downbeat falls at the speech section's end; in practice choose a music start point, then make the speech section's total length a whole number of beats by trimming air at the start). Section 2 is music: bars, energy shots, a punch on the first drop. Off-beat warnings for the speech shots are expected; read and accept them. Captions only cover the speech section; render the whole edit, caption it, the transcriber simply finds no speech in the music part.

## Travel story (story spine, beat-cut montage inside)

Brief: 45 to 60 seconds of a weekend trip to a gig abroad: train, hotel, soundcheck, the set, the morning after. Phone clips in mixed orientation, some with the owner talking to camera.

Spine: chronology. Each place gets its own short section and lands for a moment before moving on. Talking clips set their own length (`audio_db` 0, ducked music), travel shots run 1.5 to 3 seconds, cut on movement. Inside the gig section switch to the beat for a 4 to 8 bar montage. Format: 9:16; vertical phone clips fill the canvas directly, landscape ones are cropped with the cx from the logs. Grade: `natural` for the plan, and `"grade": "club"` on the gig shots. Must-haves: place names as small text when each section starts. Sound: one song as a bed, voice above it, a crowd cheer peeking through at the set. Captions for the talking parts after render.

## What carries across

Whatever the brief: the spine sets lengths and where cuts may fall, every shot is a different moment with a note saying why, the hook is in the first second, text stays in the safe area, the ending resolves, and the review loop (contact sheet, Gemini, verify, fix) runs before anything goes to the owner.
