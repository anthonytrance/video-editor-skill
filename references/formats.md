# Destinations and designs

Pick the destination first, then the design that makes the most of it. The format is a creative choice, not a default: the same night can be a full-screen 9:16 Reel, a framed square Reel that keeps both DJs in shot, a 4:5 carousel of three short moments, or a 16:9 YouTube recap. Several deliverables from one shoot are normal; make one plan per deliverable.

Platform facts below were checked on 2026-11-10. Specs change, so recheck with the web-research skill when one decides an edit.

## What each destination does with the picture

**Instagram Reel** (`"destination": "reel"`). Plays full screen. Meta's publishing docs accept almost any aspect ratio for Reels but recommend 9:16 "to avoid cropping or blank space"; 3 seconds to 15 minutes, 23 to 60 fps, H.264 or HEVC, AAC (Meta, IG User Media reference). In the feed a Reel is previewed in a 4:5 window from its centre (1080x1350 of 1080x1920), and the profile grid shows a 3:4 centre crop (Planoly's guide to the vertical grid, 2025); the in-app "Adjust preview" can move the grid crop. So the hook frame and key text should read inside the central 4:5 area. The UI-safe area (text between y 269 and 1248 on 1920) already sits inside it.

**Instagram Story** (`story`). Full screen 9:16, video 3 to 60 seconds per story (Meta, IG User Media reference). Stickers, polls and links are added in the app, so leave room for them if planned.

**Instagram carousel** (`carousel`, 1080x1350). Up to 20 images or videos (Meta, Content Publishing). Every item is cropped to the first item's ratio, default 1:1 (same page); feed images must lie between 4:5 and 1.91:1 (IG User Media). A Reel can't be a carousel item (IG User Media). Video slides are reported to run up to 60 seconds each (Storrito, 2026; not in Meta's docs). 4:5 portrait takes the most feed space. Design the slides as a set: slide 1 is the hook and the grid thumbnail, each slide is its own short plan at the same canvas, and the swipe is the cut, so each slide should end on a moment that makes the next one worth a swipe. Good uses: "three moments from the night", before and after, one track per slide, a photo cover followed by video.

**Feed video** (`feed`, 1080x1350). A single non-Reel post; the same 4:5 logic, no full-screen UI on top.

**TikTok** (`tiktok`). 9:16 full screen; third-party guides say square and landscape uploads are shown with bars (not confirmed on TikTok's own help pages as of this check).

**YouTube Shorts** (`shorts`). YouTube Help: up to 3 minutes, square or vertical. 9:16 fills the player; a 1:1 Short is a real option when the footage is wide.

**YouTube** (`youtube`, 1920x1080). Long-form recaps, full sets, vlogs in 16:9.

**Facebook Reels** use the reel preset: 9:16 is the consistent recommendation; reports that the app accepts any ratio are unconfirmed on Meta's help pages.

## Designs within a destination

**Full bleed.** The picture fills the canvas. Best for close, energetic footage where a 9:16 window holds the subject. The default.

**Framed picture.** A square, 4:5 or 16:9 picture inside a 9:16 canvas, with a designed background: a brand colour, or the same shot blurred and darkened behind it (`"background": "blur"`). Use it when the moment is wide (two DJs far apart, a full crowd, a stage), when the footage is landscape and a 9:16 crop would throw away the story, or as a deliberate look for a recap or a series. The bands above and below are the natural place for the headline and the logo. It still fills the screen, so it isn't letterboxing: the background is part of the design. Plan: `"picture": {"size": [1080, 1080], "y": 400, "background": "blur"}`.

**Mixed.** Framed for wide moments, full bleed for close ones, switching per shot (`"picture": "full"` on a shot). Use the switch on purpose, such as framed for the scene-setting opening and full bleed from the drop.

**Not yet built:** split screen (two shots stacked, such as both DJs at once) and picture-in-picture. Both need a renderer extension; ask before building.

## Choosing

Start from the material and the purpose. Footage that is close and vertical-friendly suits a full-bleed Reel. Wide or landscape footage with the story across the frame suits a framed Reel, a 4:5 feed post or a carousel, or a 16:9 YouTube video. Several separate moments that don't need to flow suit a carousel. Time-limited news (tonight, tickets, "see you Saturday") suits a Story. If two destinations matter, design for the stricter one first (usually the 9:16 Reel), then make a second plan for the other with its own framing and text positions; never squeeze one render into every destination.

## Sources

Meta, IG User Media reference: https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media
Meta, Content Publishing: https://developers.facebook.com/documentation/instagram-platform/content-publishing
YouTube Help, upload YouTube Shorts: https://support.google.com/youtube/answer/12779649
Planoly, guide to Instagram's vertical grid: https://www.planoly.com/blog/guide-to-instagrams-new-vertical-grid
Storrito, 20-slide carousels: https://storrito.com/resources/how-instagrams-20-slide-carousels-work-and-what-the-new-limits-are/
