---
name: happy
description: Automate happyoyster.cn/create benchmark runs. Use when the user asks to run a case on Happy Oyster (e.g. "run case_XXX on happy", "用happy跑case_XXX"). Fully JS-driven (fetch + DataTransfer for image upload, no pyautogui coordinates).
---

# Happy Oyster Benchmark Automation

Automates one benchmark case on https://www.happyoyster.cn/create. Input: `case_<id>.json` from the dataset's `cases/` directory. Output: `happy_video/case_<id>.mp4` under the repo root.

Paths below assume the repo is checked out and `cd`-ed into. Replace `<repo>` with the absolute checkout path when calling scripts from a non-repo cwd.

## Key insight

**happyoyster.cn does NOT enforce Private Network Access** (unlike Project Genie). `fetch('http://127.0.0.1:18888/...')` works from the page, so images upload via `DataTransfer` — no native file dialog, no pyautogui coordinates, no window-handle juggling. Every interaction is a single browser-automation call.

## Prerequisite

The local HTTP server must be running, serving the directory that contains the dataset's `images/` tree. From the repo root:

```bash
python serve.py 18888
```

Verify:
```bash
curl -o /dev/null -s -w "%{http_code}\n" http://127.0.0.1:18888/data/images/case_2.jpg
```
Should return `200`.

## Before each new case

**Kill any leftover `auto_interact.py` process** before navigating to `/create`. Stale key-press processes will leak into the next world.

```powershell
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
    $cmd = (Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmd -like "*auto_interact*") { Stop-Process -Id $_.Id -Force }
}
```

## Workflow

### 1. Navigate & inject prompt

```js
const env = `<environment_prompt>`;
const char = `<character_prompt>`;
const prompt = `Environment: ${env}\n\nCharacter: ${char}\n\nMaintain visual consistency with the reference image. No HUD. No UI elements.`;
const ta = document.querySelector('textarea');
const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
setter.call(ta, prompt);
ta.dispatchEvent(new Event('input', { bubbles: true }));
```

For open-world navigation cases, append `no obstacles, move freely` to the environment clause — Happy Oyster otherwise tends to spawn blocking geometry.

### 2. Upload image (fetch + DataTransfer)

```js
(async () => {
  const url = 'http://127.0.0.1:18888/data/images/case_<id>.jpg';
  const blob = await (await fetch(url)).blob();
  const file = new File([blob], 'case_<id>.jpg', { type: 'image/jpeg' });
  const input = document.querySelector('input[type=file]');
  const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
  input.dispatchEvent(new Event('change', { bubbles: true }));
  window.__uploadDone = `uploaded ${file.size}`;
})();
```
Use the path in `settings.initial_image` (the public dataset has no perspective subdirs). Wait ~1s, then screenshot to verify a thumbnail appears in the Image slot.

### 3. Flip perspective if first_person

Default is Third person. If the case is `first_person`, click the toggle once:
```js
const persp = [...document.querySelectorAll('button,[role=button]')]
  .find(b => b.textContent.trim() === 'Third person');
if (persp) persp.click();
```

### 4. Click send

Small (~36×36) unlabeled icon button in the bottom-right of the prompt bar. Find by geometry, not pixel coordinates:
```js
const send = [...document.querySelectorAll('button,[role=button]')].filter(b => {
  const r = b.getBoundingClientRect();
  return r.width >= 30 && r.width <= 45 && r.height >= 30 && r.height <= 45
         && r.top > 600 && !b.textContent.trim();
});
if (send.length === 1) send[0].click();
```
URL changes to `/explore/wander/...`. Recording auto-starts with a ~55s timer.

### 5. Start auto_interact in background

Start **immediately** once the URL leaves `/create` — the script internally waits for `t2.png` to appear before sending keys.

```bash
python auto_interact.py data/cases/case_<id>.json happy_oyster/t2.png 3
```
- `happy_oyster/t2.png` — single "A" key template (not Genie3's WASD cluster `t.png`).
- `3` — seconds per turn. Recording is time-limited so don't bump this above 4.

### 6. Wait for recording to end

Poll the active tab every ~10s until the URL transitions from `/explore/wander/...` to `/end/travel/...`. Typical duration: ~90-100s total from send to end (30-60s world generation + ~55s recording).

If the page shows `99%` loading text for more than ~2 minutes without showing `REC`, navigate back to `/create` and retry from step 1.

### 7. Download

```js
[...document.querySelectorAll('button,[role=button]')]
  .find(b => b.getAttribute('aria-label') === 'Download').click();
```

A "Download options" modal appears. Select "Without BGM", then click Download in the modal:
```js
const noBgm = [...document.querySelectorAll('*')]
  .find(d => d.textContent.trim() === 'Without BGM' && d.getBoundingClientRect().width > 50);
let el = noBgm; while (el && !['DIV','BUTTON'].includes(el.tagName)) el = el.parentElement;
el.click();
setTimeout(() => {
  [...document.querySelectorAll('button,[role=button]')]
    .find(b => b.textContent.trim() === 'Download').click();
}, 500);
```
A "Preparing download..." banner shows at the top. Server rendering takes 20-60s.

### 8. Move file

File downloads to `~/Downloads/` as `<world_title>.mp4` (e.g. `CanineUrbanPulse.mp4`, `The Corinthian Archive.mp4`). Find the newest non-`Genie*` mp4 and move:
```bash
mv "<Downloads>/<newest_title>.mp4" "happy_video/case_<id>.mp4"
```

### 9. Update progress

Optional — if you maintain a `happy_progress.json`:
```python
import json
with open('happy_progress.json') as f: p = json.load(f)
p['case_<id>']['status'] = 'done'
with open('happy_progress.json','w') as f: json.dump(p, f, indent=2)
```

## Things that do NOT work (and why)

- **pyautogui coordinate clicks**: Unreliable. Multiple Chrome windows for the same tab can coexist; their rects change when `SW_RESTORE` fires; the Image button's screen position varies with toolbar height, DevTools state, and window maximization. Use the JS-only flow instead.
- **`mcp__claude-in-chrome__upload_image`**: Only accepts `imageId` from prior screenshots, not disk paths.
- **Inline base64 injection**: A 500 KB image is ~680 KB of base64 — too long to paste into a single JS-evaluation call.

## Gotchas

- Recording is a fixed ~55s timer. With `KEY_DURATION=3`, cases with >15 navigation turns won't fit.
- The "Without BGM" click must land on the parent `<div>`, not the inner text node — walk up to the first DIV/BUTTON ancestor.
- After download, the URL stays at `/end/travel/...`. Navigate fresh to `/create` for the next case.
- Different cases produce different world_title names — find by "newest non-Genie mp4" rather than an expected filename.

## Files referenced

- `auto_interact.py` — shared keyboard driver (accepts template path as 2nd arg, turn duration as 3rd)
- `happy_oyster/t2.png` — Happy Oyster single-"A" key template (~636 bytes)
- `serve.py` — local HTTP server with CORS + Private Network Access headers
- `happy_video/` — output directory (create if missing)
