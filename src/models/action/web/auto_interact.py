"""
Keyboard layer for web world-model benchmark runs (Windows).

Usage: python auto_interact.py <case_json> [template_png] [key_duration_s]
  e.g. python auto_interact.py data/cases/case_1.json genie3/t.png 5

Flow:
  1. Read navigation interactions from the case JSON (type == "navigation").
  2. Poll the screen with OpenCV template matching until the in-world UI appears
     (WASD cluster for Genie3 / single "A" for Happy Oyster).
  3. Press each turn's keys for `key_duration` seconds, no gap between turns.
  4. Two always-on-top overlays show the match score and the active key.

Hotkey:
  F12 : force quit
"""

import json
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2
import numpy as np
import mss
from pathlib import Path
from pynput.keyboard import Key, Controller, Listener

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Paths
BASE_DIR = Path(__file__).parent
TEMPLATE_PATH = BASE_DIR / (sys.argv[2] if len(sys.argv) > 2 else "t.png")

# Template-matching params
MATCH_THRESHOLD = 0.7
SCAN_INTERVAL = 0.2

# action token -> pynput key
KEY_MAP = {
    "W": "w",
    "A": "a",
    "S": "s",
    "D": "d",
    "left":  Key.left,
    "right": Key.right,
    "up":    Key.up,
    "down":  Key.down,
}

# Display names
KEY_DISPLAY = {
    "W": "W", "A": "A", "S": "S", "D": "D",
    "left": "LEFT", "right": "RIGHT", "up": "UP", "down": "DOWN",
}

# Hold time per turn (seconds). Override via argv[3].
KEY_DURATION = float(sys.argv[3]) if len(sys.argv) > 3 else 5

# Global state
kb = Controller()
running = True


# ══════════════════════════════════════════════════
# Top-left template-match preview window
# ══════════════════════════════════════════════════
class MatchOverlay:
    def __init__(self, template_img):
        self.root = tk.Tk()
        self.root.title("Match")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.90)
        self.root.configure(bg="#0d0d1a")
        self.root.geometry("220x180+10+10")

        self.score_label = tk.Label(
            self.root, text="score: --", font=("Consolas", 11, "bold"),
            fg="#ffaa00", bg="#0d0d1a"
        )
        self.score_label.pack(pady=(6, 2))

        # Template preview
        tk.Label(self.root, text="template", font=("Consolas", 8),
                 fg="#555555", bg="#0d0d1a").pack()
        self.tmpl_label = tk.Label(self.root, bg="#0d0d1a")
        self.tmpl_label.pack(pady=2)

        # Current screenshot preview
        tk.Label(self.root, text="screen region", font=("Consolas", 8),
                 fg="#555555", bg="#0d0d1a").pack()
        self.screen_label = tk.Label(self.root, bg="#0d0d1a")
        self.screen_label.pack(pady=2)

        # Show template (fixed)
        self._show_image(self.tmpl_label, template_img, size=(100, 25))

    def _show_image(self, label, img_bgr_or_bgra, size=(100, 25)):
        """Convert a cv2 image and show it on a label."""
        if img_bgr_or_bgra is None:
            return
        ch = img_bgr_or_bgra.shape[2] if len(img_bgr_or_bgra.shape) == 3 else 1
        if ch == 4:
            img_rgb = cv2.cvtColor(img_bgr_or_bgra, cv2.COLOR_BGRA2RGB)
        else:
            img_rgb = cv2.cvtColor(img_bgr_or_bgra, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb).resize(size, Image.NEAREST)
        photo = ImageTk.PhotoImage(pil_img)
        label.config(image=photo)
        label._photo = photo  # prevent GC

    def update(self, score, screen_region_img):
        color = "#00ff88" if score >= MATCH_THRESHOLD else "#ff4444"
        self.score_label.config(text=f"score: {score:.3f}", fg=color)
        self._show_image(self.screen_label, screen_region_img, size=(100, 25))
        self.root.update()

    def close(self):
        self.root.destroy()


# ══════════════════════════════════════════════════
# Top-right status window
# ══════════════════════════════════════════════════
class StatusOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("auto_interact")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg="#1a1a2e")

        # Top-right corner
        self.root.geometry("280x90+1630+10")

        self.title_label = tk.Label(
            self.root, text="Auto-Interact", font=("Consolas", 10),
            fg="#888888", bg="#1a1a2e", anchor="w"
        )
        self.title_label.pack(fill="x", padx=8, pady=(6, 0))

        self.status_label = tk.Label(
            self.root, text="IDLE", font=("Consolas", 14, "bold"),
            fg="#00ff88", bg="#1a1a2e", anchor="w"
        )
        self.status_label.pack(fill="x", padx=8)

        self.detail_label = tk.Label(
            self.root, text="", font=("Consolas", 10),
            fg="#aaaaaa", bg="#1a1a2e", anchor="w"
        )
        self.detail_label.pack(fill="x", padx=8, pady=(0, 6))

    def update(self, status, detail="", color="#00ff88"):
        self.status_label.config(text=status, fg=color)
        self.detail_label.config(text=detail)
        self.root.update()

    def close(self):
        self.root.destroy()


# ══════════════════════════════════════════════════
# Core logic
# ══════════════════════════════════════════════════
def parse_action(action_str):
    """Parse a case action string into a list of pynput keys."""
    parts = action_str.split("+")
    keys = []
    for p in parts:
        p = p.strip()
        if p in KEY_MAP:
            keys.append(KEY_MAP[p])
        else:
            print(f"  [WARN] unknown key '{p}', skipped")
    return keys


def get_action_display(action_str):
    """Display name for an action."""
    parts = action_str.split("+")
    names = [KEY_DISPLAY.get(p.strip(), p.strip()) for p in parts]
    return " + ".join(names)


def load_nav_interactions(case_path):
    """Load navigation-type interactions from a case JSON."""
    with open(case_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    interactions = data.get("interactions", [])
    nav = [i for i in interactions if i["type"] == "navigation"]
    return data.get("id", "?"), nav


def grab_scan_region():
    """Grab the bottom-left 1/4W x 1/4H region of the primary monitor."""
    with mss.mss() as sct:
        m = sct.monitors[1]
        w = m["width"] // 4
        h = m["height"] // 4
        region = {
            "left": m["left"],
            "top": m["top"] + m["height"] - h,
            "width": w,
            "height": h,
        }
        return np.array(sct.grab(region))


def to_gray(img):
    """Convert to grayscale based on channel count."""
    if len(img.shape) == 2:
        return img
    ch = img.shape[2]
    if ch == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def match_template(screen_img, template_img):
    """Template match; return the max normalized correlation."""
    gray_screen = to_gray(screen_img)
    gray_template = to_gray(template_img)
    if (gray_template.shape[0] > gray_screen.shape[0] or
            gray_template.shape[1] > gray_screen.shape[1]):
        return 0.0
    result = cv2.matchTemplate(gray_screen, gray_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val


def wait_for_wasd(template, status_overlay=None, match_overlay=None):
    """Block until the template appears on screen or interrupted."""
    global running
    while running:
        screen = grab_scan_region()
        score = match_template(screen, template)
        if match_overlay:
            match_overlay.update(score, screen)
        if score >= MATCH_THRESHOLD:
            print(f"  [MATCH] in-world UI detected (score={score:.3f})")
            return True
        if status_overlay:
            status_overlay.update("WAITING...", f"score={score:.3f}", "#ffaa00")
        time.sleep(SCAN_INTERVAL)
    return False


def execute_turn(keys, duration, overlay=None, label=""):
    """Press a set of keys, hold for `duration` seconds, then release."""
    global running
    for k in keys:
        kb.press(k)
    elapsed = 0.0
    while elapsed < duration and running:
        remaining = duration - elapsed
        if overlay:
            overlay.update(label, f"{remaining:.1f}s remaining", "#00ccff")
        time.sleep(0.1)
        elapsed += 0.1
    for k in keys:
        kb.release(k)


def on_press(key):
    global running
    if key == Key.f12:
        running = False
        print("\n[STOP] F12 interrupted")


def main():
    global running

    if len(sys.argv) < 2:
        print("Usage: python auto_interact.py <case_json> [template_png] [key_duration_s]")
        print("Example: python auto_interact.py data/cases/case_1.json genie3/t.png 5")
        sys.exit(1)

    case_path = Path(sys.argv[1])
    if not case_path.is_absolute():
        case_path = Path.cwd() / case_path

    if not case_path.exists():
        print(f"[ERROR] File not found: {case_path}")
        sys.exit(1)

    case_id, nav_interactions = load_nav_interactions(case_path)
    if not nav_interactions:
        print(f"[ERROR] Case {case_id} has no navigation interactions")
        sys.exit(1)

    print(f"{'='*50}")
    print(f"Case {case_id} -- {len(nav_interactions)} navigation turns")
    for i, inter in enumerate(nav_interactions):
        print(f"  Turn {inter['turn']}: {inter['action']}")
    print(f"{'='*50}")

    # Check template
    if not TEMPLATE_PATH.exists():
        print(f"[ERROR] Template not found: {TEMPLATE_PATH}")
        sys.exit(1)

    template = cv2.imread(str(TEMPLATE_PATH), cv2.IMREAD_UNCHANGED)
    if template is None:
        print("[ERROR] Failed to read template")
        sys.exit(1)

    # Create overlays
    match_overlay = MatchOverlay(template)
    overlay = StatusOverlay()
    overlay.update("LOADED", f"Case {case_id} | {len(nav_interactions)} turns", "#00ff88")

    # Start keyboard listener (F12 to interrupt)
    listener = Listener(on_press=on_press)
    listener.start()

    # Wait for the in-world UI (world generation done)
    print(f"\n[WAIT] Waiting for world generation (UI to appear)...")
    overlay.update("WAITING...", "World generating...", "#ffaa00")
    if not wait_for_wasd(template, overlay, match_overlay):
        overlay.close()
        listener.stop()
        return

    # Execute turns, no gap in between
    total = len(nav_interactions)
    for i, inter in enumerate(nav_interactions):
        if not running:
            print("Interrupted")
            break

        action = inter["action"]
        keys = parse_action(action)
        display = get_action_display(action)
        if not keys:
            print(f"\n[{i+1}/{total}] Turn {inter['turn']}: {action} -- no valid keys, skipped")
            continue

        overlay.update(
            f"[{i+1}/{total}] {display}",
            f"Turn {inter['turn']} | {KEY_DURATION}s",
            "#00ccff"
        )

        print(f"\n[{i+1}/{total}] Turn {inter['turn']}: {action} -- pressing for {KEY_DURATION}s")
        execute_turn(keys, KEY_DURATION, overlay, f"[{i+1}/{total}] {display}")
        print(f"[{i+1}/{total}] Keys released")

    # Done
    running = False
    overlay.update("DONE", f"Case {case_id} complete", "#00ff88")
    print(f"\n{'='*50}")
    print(f"Case {case_id} -- all interactions done")
    print(f"{'='*50}")

    time.sleep(2)
    overlay.close()
    match_overlay.close()
    listener.stop()


if __name__ == "__main__":
    main()
