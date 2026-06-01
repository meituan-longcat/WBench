---
name: genie3
description: Automate Project Genie (labs.google) benchmark runs. Use when the user asks to run a case on Genie3 (e.g. "run case_XXX on genie3", "用genie3跑case_XXX"). Uses OS file-dialog upload because Genie3 enforces Private Network Access.
---

# Project Genie Benchmark Automation

Automates one benchmark case on https://labs.google/fx/projectgenie/tools/projectgenie/creation. Input: `case_<id>.json` from the dataset's `cases/` directory. Output: `save_video/case_<id>.mp4` under the repo root.

Paths below assume the repo is checked out and `cd`-ed into. Replace `<repo>` with the absolute checkout path when calling scripts from a non-repo cwd.

## Key insight

**Project Genie enforces Private Network Access**, so `fetch('http://127.0.0.1:...')` from the page is blocked by Chrome. Images must therefore be uploaded through the OS file dialog — `genie3/upload_image_full.py` finds the Chrome window, clicks the "+" button, and pastes the image path into the dialog. Everything else (prompt injection, "Create world" click, video download) is JS-driven.

## Prerequisite

The local HTTP server only needs to run if you also intend to drive Happy Oyster in the same session. For Genie3 alone the script reads the image directly from disk; no server is required.

```bash
python serve.py 18888   # optional, only if cross-platform session
```

## Workflow

### 1. Navigate

Open Chrome to the creation page, give it ~3s to hydrate. Make sure the Chrome window title contains `Project Genie` — the upload script greps the window list for that.

### 2. Inject prompts

Two textareas: `environment_prompt` and `character_prompt`. Both are React-controlled, so set via the native setter + bubbling `input` event:

```js
function setReact(el, val) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  setter.call(el, val);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}
const [envTa, charTa] = document.querySelectorAll('textarea');
setReact(envTa, `<environment_prompt>`);
setReact(charTa, `<character_prompt>`);
```

### 3. Upload initial frame

```bash
python genie3/upload_image_full.py <repo>/data/images/case_<id>.jpg
```

What the script does:
1. Copies the path to the clipboard.
2. Finds the Chrome window with title `Project Genie`, brings it to foreground.
3. Clicks the "+" button (viewport ~485, 657, scaled to the actual window size).
4. Watches for the Windows file dialog (`#32770`). If the "I agree" Notice overlay appears first, clicks it and re-clicks "+".
5. When the file dialog appears, `Ctrl+A` `Ctrl+V` Enter to submit the path.

The Chrome viewport is assumed ~1568x726 — if your zoom level or window size differs significantly you may need to retune the `vp_w`/`vp_h` constants in the script.

### 4. Set perspective (if needed)

The perspective control is a single button that cycles labels (Third → First → ...). Click until `getAttribute('aria-pressed')` or the button text matches `settings.perspective`.

### 5. Click "Create world"

Find the primary CTA by text match (`Create world`) and click. URL changes; world generation starts.

### 6. Start auto_interact in background

Start **immediately** after clicking — the script internally waits for `t.png` (WASD cluster) to appear before sending keys.

```bash
python auto_interact.py data/cases/case_<id>.json genie3/t.png 5
```
- `genie3/t.png` — WASD button cluster template (33x77 px at 1920x1080).
- `5` — seconds per turn. Genie3 has no hard recording cap so 5s/turn is the standard.

### 7. Wait for "Thanks for exploring!"

The page transitions to a thank-you screen once interactions complete. The download button appears at approximately screen coordinate `(684, 534)` on 1920x1080 — click via JS (preferred) or pyautogui as fallback:

```js
[...document.querySelectorAll('button')]
  .find(b => /download/i.test(b.textContent || b.getAttribute('aria-label') || '')).click();
```

### 8. Move file

File downloads to `~/Downloads/Genie<hash>.mp4`. Find the newest `Genie*.mp4` and move:
```bash
mv "<Downloads>/Genie<latest>.mp4" "save_video/case_<id>.mp4"
```

### 9. Update progress

Optional — if you maintain a `progress.json`:
```python
import json
with open('progress.json') as f: p = json.load(f)
p['case_<id>']['status'] = 'done'
with open('progress.json','w') as f: json.dump(p, f, indent=2)
```

## Gotchas

- The first time a fresh browser profile opens Project Genie, a "Notice" overlay covers the page until you click "I agree". `upload_image_full.py` handles this after 2s of waiting for the file dialog, but if the layout changes the heuristic ((944, 444) viewport coord) may need to be retuned.
- Two Chrome windows with `Project Genie` in the title (e.g. main window + DevTools-undocked instance) will confuse the upload script — close the extra one or modify the lookup to pick by largest area.
- If `auto_interact.py` is started before "Create world" is clicked, it will sit at `WAITING...` until the WASD cluster appears. That's fine; the polling is cheap.
- Some Genie3 cases trigger a content-policy refusal at world generation. The download step will time out — fail the case rather than retrying indefinitely.

## Files referenced

- `auto_interact.py` — shared keyboard driver (template + duration as args)
- `genie3/t.png` — WASD button-cluster template (33x77, ~1580 bytes)
- `genie3/upload_image_full.py` — Chrome "+" click + Windows file-dialog handler
- `save_video/` — output directory (create if missing)
