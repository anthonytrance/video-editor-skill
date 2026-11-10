# Brand file

`~/.video-editor/brand.json` (or `VIDEO_EDITOR_HOME`, or `"brand"` in a plan) holds what belongs to the owner, so the scripts stay usable by anyone. Every key is optional.

```json
{
  "name": "Artist name",
  "grade": "club",
  "assets": {
    "regular": "D:/brand/Lato-Regular.ttf",
    "bold": "D:/brand/Lato-Bold.ttf",
    "logo": "D:/brand/logo.png",
    "label-logo": {"file": "D:/brand/label-logo.mov", "crop": "940:360:180:180",
                   "note": "animated; frames 0 to 4s animate in, settled from 8s"}
  },
  "text": {
    "headline": {"font": "bold", "size": 58},
    "detail": {"font": "regular", "size": 48},
    "case": "upper",
    "letter_note": "Short uppercase lines, white with a soft shadow, centred."
  }
}
```

`grade` is the default look for plans that don't name one. `assets` maps short names to files; plans use the names (`"font": "bold"`, `"video": "label-logo"`). An asset given as an object carries defaults that the plan may override, such as a `crop` that trims transparent margins from a logo. Keep the assets themselves in a stable media folder outside the skill. `text` is guidance for the agent writing plans; the renderer reads only fonts and sizes given in the plan.

Gemini calls need an OpenRouter key in `OPENROUTER_API_KEY` (or the Hermes `.env`). `VIDEO_EDITOR_GEMINI` overrides the model, default `google/gemini-3.8-flash`.
