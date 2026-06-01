# World-Model Benchmark Pipeline

Automation pipeline for evaluating generative world-model products on a fixed benchmark
of navigation cases. Currently targets two platforms:

- **Project Genie** — https://labs.google/fx/projectgenie/tools/projectgenie/creation
- **Happy Oyster** — https://www.happyoyster.cn/create

For every case the pipeline fills in the text prompts, uploads the initial frame,
clicks "Create", simulates the requested key sequence in the resulting world, and
saves the rendered video.

> **How this is driven.** These are *web products* with no weights or API, so the
> browser steps are automated with **[Claude Code](https://claude.com/claude-code)**
> plus the **claude-in-chrome** browser MCP — i.e. you need a Claude account and a
> Chrome session connected to that MCP. The bundled `.claude/skills/` turn a
> single case into a natural-language ask (`run case_1 on genie3`). The keyboard
> layer (`auto_interact.py`) is plain local automation and needs no account; if
> you'd rather not use Claude, you can drive the browser steps by hand (DevTools
> console) or with any CDP/Playwright host instead — see
> [Running manually](#running-manually).

## Layout

```
src/models/action/web/
├── README.md
├── requirements.txt
├── auto_interact.py            Shared keyboard layer (template wait + key presses)
├── serve.py                    Local HTTP server (CORS + Private Network Access)
├── genie3/
│   ├── t.png                   WASD button-cluster template (33x77 @ 1920x1080)
│   └── upload_image_full.py    Genie3 image upload via the OS file dialog
├── happy_oyster/
│   ├── t2.png                  Single-"A" key template
│   └── batch_happy_oyster.py   Batch driver for Happy Oyster runs
└── .claude/skills/             Claude Code skills ("run case_<id> on genie3/happy")
    ├── genie3/SKILL.md
    └── happy/SKILL.md
```

This drives **web-product** action models (no weights/API). For programmatic
action models, see the sibling `actions.py` / `example_model.py`. The dataset
(case JSONs + frames) lives under the repo's `data/`; see
[Dataset format](#dataset-format) below.

## Architecture

The pipeline is split into two cooperating layers.

1. **Browser layer.** Everything that happens inside the browser tab — navigation,
   prompt injection, image upload, perspective toggle, "Create world" click, final
   video download — is driven by JavaScript snippets executed against a connected
   Chrome session (e.g. via Chrome DevTools Protocol or a browser-automation MCP).
   The two platforms differ on one point only: Happy Oyster accepts cross-origin
   `fetch()` from `127.0.0.1`, so images can be injected straight into the file
   `<input>` via `DataTransfer`; Project Genie enforces Private Network Access and
   blocks that path, so the OS file dialog is driven instead by
   [`genie3/upload_image_full.py`](genie3/upload_image_full.py).

2. **Keyboard layer (`auto_interact.py`).** Runs as a background subprocess started
   right after the "Create world" click. Polls the screen with OpenCV template
   matching until the in-world UI appears (WASD cluster for Genie3, single "A" key
   for Happy Oyster), then presses the keys listed in the case's
   `interactions[]`. Each turn holds for `KEY_DURATION` seconds (default 5,
   override via `argv[3]`). Two always-on-top Tk overlays show the current match
   score and the active key. **F12** force-quits.

## Install

Python 3.10+ on Windows (the keyboard/window-dialog layer uses `pynput`,
`pyautogui`, `pywin32`, `mss`, which are Windows-specific here).

```powershell
pip install -r requirements.txt
```

Verify the templates can be read:

```powershell
python -c "import cv2; print(cv2.imread('genie3/t.png').shape)"
```

## Dataset format

Each case is a single JSON file. Minimum fields the pipeline reads:

```json
{
  "id": 1,
  "environment_prompt": "...",
  "character_prompt": "...",
  "settings": {
    "perspective": "third_person",
    "initial_image": "images/case_1.jpg"
  },
  "interactions": [
    { "turn": 1, "type": "navigation", "action": "W" },
    { "turn": 2, "type": "navigation", "action": "right" },
    { "turn": 3, "type": "navigation", "action": "W+D" }
  ]
}
```

Supported `action` tokens (combine with `+`):

| token | key |
|---|---|
| `W` `A` `S` `D` | character motion |
| `left` `right` `up` `down` | arrow keys |

Only `type: "navigation"` interactions are executed. The other types
(`subject_action`, `event_edit`, `perspective_switch`) are silently skipped.

Initial-frame images live under `data/images/case_<id>.jpg` (the path in each
case's `settings.initial_image`) and are served over HTTP at
`http://127.0.0.1:18888/...`. The public dataset has no perspective subdirs —
read `settings.initial_image` directly rather than assuming `first_person/`
or `third_person/`.

## Running with Claude Code (primary path)

**Prerequisites:** a Claude account, [Claude Code](https://claude.com/claude-code)
opened in this checkout, and the **claude-in-chrome** browser MCP connected to a
Chrome session (this is what performs the in-tab prompt injection, image upload,
"Create world" click, and download). On Windows, also `pip install -r
requirements.txt` so the keyboard layer can run.

The repo ships two project-level skills under `.claude/skills/`. With the above
in place, drive a single case end-to-end with a natural-language ask:

- `run case_1 on genie3` → invokes the **genie3** skill
- `run case_1 on happy` → invokes the **happy** skill

Each skill encodes the per-platform browser flow, the right `auto_interact.py`
template + turn duration, and the download/rename hand-off.

## Running manually

Use this if you don't want to use Claude — drive the browser steps yourself
(DevTools console, or a CDP/Playwright host). `auto_interact.py` is identical
either way.

### 1. Start the local image server

From a directory whose subtree contains your `images/` folder:

```powershell
python serve.py 18888
```

This serves the current working directory with the headers required by both
platforms (`Access-Control-Allow-Origin: *`, `Access-Control-Allow-Private-Network: true`).

### 2. Drive the browser

Open Chrome at the platform's creation page, attach a JavaScript console
(DevTools or a browser-automation MCP), and run the per-platform flow:

#### Project Genie

1. Navigate to the creation page and wait for hydration.
2. Inject `environment_prompt` and `character_prompt` into their textareas using
   the native `value` setter + bubbling `input` event (React controlled inputs).
3. Trigger the OS file dialog by clicking the "+" button, then upload the initial
   frame:

   ```powershell
   python genie3/upload_image_full.py path\to\data\images\case_1.jpg
   ```

   The script finds the Chrome window titled `Project Genie`, computes the "+"
   button position, clicks it, waits for the Windows file dialog (`#32770`), and
   submits the path via clipboard paste + Enter. It also handles the
   first-time "I agree" Notice overlay.
4. Click "Create world" via JavaScript.
5. Start the keyboard layer immediately:

   ```powershell
   python auto_interact.py path\to\cases\case_1.json genie3\t.png 5
   ```

6. When the in-browser UI shows "Thanks for exploring!", click the download
   button. The file lands in `Downloads/Genie<hash>.mp4`; rename it to
   `case_<id>.mp4`.

#### Happy Oyster

1. Kill any leftover `auto_interact.py` process from the previous case
   (stale key presses will leak into the new world).
2. Navigate to `https://www.happyoyster.cn/create` and wait ~3s.
3. Inject the combined prompt into the single textarea:

   ```js
   const prompt = `Environment: ${env}\n\nCharacter: ${char}\n\nMaintain visual consistency with the reference image. No HUD. No UI elements.`;
   const ta = document.querySelector('textarea');
   const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
   setter.call(ta, prompt);
   ta.dispatchEvent(new Event('input', { bubbles: true }));
   ```

4. Upload the initial frame via `fetch` + `DataTransfer`:

   ```js
   const url = 'http://127.0.0.1:18888/data/images/case_1.jpg';
   const blob = await (await fetch(url)).blob();
   const file = new File([blob], 'case_1.jpg', { type: 'image/jpeg' });
   const input = document.querySelector('input[type=file]');
   const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
   input.dispatchEvent(new Event('change', { bubbles: true }));
   ```

5. If `settings.perspective` is `first_person`, click the perspective button
   once (default state is Third person).
6. Click the small ~36x36 unlabeled send button in the prompt bar. URL changes
   to `/explore/wander/...`.
7. Start the keyboard layer immediately (with `t2.png` and 3s turn duration —
   Happy Oyster recordings are time-limited):

   ```powershell
   python auto_interact.py path\to\cases\case_1.json happy_oyster\t2.png 3
   ```

8. Poll the URL every ~10s. When it changes to `/end/travel/...`, the recording
   ended.
9. Click the orb-shaped Download button (`aria-label="Download"`), then in the
   modal select "Without BGM" and click final "Download". The video downloads
   as `<world_title>.mp4` after ~20-60s; move it to `case_<id>.mp4`.

[`happy_oyster/batch_happy_oyster.py`](happy_oyster/batch_happy_oyster.py) is a
skeleton that wires steps 1, 7, and the download-rename hand-off; the browser
steps (2-6, 8-9) still need to be driven from your JS console / automation host.

## Platform differences at a glance

| | Project Genie | Happy Oyster |
|---|---|---|
| Image upload | Blocked by PNA — OS file dialog via `upload_image_full.py` | `fetch` + `DataTransfer` |
| Prompts | 2 textareas (env + character) | 1 combined textarea |
| Perspective | Single cycling button | Toggle button flips label |
| Wait template | `genie3/t.png` (WASD cluster, 33x77) | `happy_oyster/t2.png` (single "A") |
| Turn duration | 5s | 3s (recording time-limited) |
| Output filename | `Genie<hash>.mp4` | `<world_title>.mp4` |

## Tuning `auto_interact.py`

Constants at the top of the file:

| constant | default | meaning |
|---|---|---|
| `MATCH_THRESHOLD` | `0.7` | minimum normalized cross-correlation to declare a match |
| `SCAN_INTERVAL` | `0.2` s | poll cadence while waiting for the template |
| `KEY_DURATION` | `5` s (argv[3] overrides) | hold time per turn |

The script scans only the bottom-left 1/4 of the primary monitor. If you run at
a resolution other than 1920x1080 the templates may need to be re-captured.

## License

MIT — see the repository [LICENSE](../../../../LICENSE).
