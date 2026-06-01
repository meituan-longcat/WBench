"""Full image upload (Windows): click "+" button, handle Notice, fill file dialog.

Usage: python upload_image_full.py <image_path> [chrome_window_title]
  <image_path>          absolute path to the first-frame image (e.g. data/images/case_1.jpg)
  [chrome_window_title] window title to target (default: "Project Genie")
"""
import time, sys, subprocess
import pyautogui
import win32gui, win32con

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)
filepath = sys.argv[1]

# Copy path to clipboard
subprocess.run(['powershell', '-command', f'Set-Clipboard -Value "{filepath}"'], check=True)
print(f"Clipboard set")

# Find Chrome window with Project Genie
TITLE_KW = sys.argv[2] if len(sys.argv) > 2 else 'Project Genie'
chrome_hwnd = None
def find_chrome(hwnd, extra):
    global chrome_hwnd
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if TITLE_KW in title and chrome_hwnd is None:
            chrome_hwnd = hwnd
win32gui.EnumWindows(find_chrome, None)

if not chrome_hwnd:
    print("Chrome not found!"); sys.exit(1)

rect = win32gui.GetWindowRect(chrome_hwnd)
win_x, win_y, win_x2, win_y2 = rect
win_w = win_x2 - win_x
print(f"Chrome: {rect}, size={win_w}x{win_y2-win_y}")

win32gui.SetForegroundWindow(chrome_hwnd)
time.sleep(0.5)

# Calculate "+" button screen position
# Viewport 1568px wide, button at x=485, y=657
vp_w, vp_h = 1568, 726
toolbar_h = 100  # approx browser toolbar height
scale_x = win_w / vp_w
scale_y = (win_y2 - win_y - toolbar_h) / vp_h

btn_x = int(win_x + 485 * scale_x)
btn_y = int(win_y + toolbar_h + 657 * scale_y)
print(f"Clicking + at ({btn_x}, {btn_y})")
pyautogui.click(btn_x, btn_y)
time.sleep(1)

def find_dialog_class(cls_name=None, title_kws=None):
    result = []
    def cb(hwnd, extra):
        if not win32gui.IsWindowVisible(hwnd): return
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        if cls_name and cls == cls_name:
            result.append((hwnd, title, cls))
        elif title_kws and any(k in title for k in title_kws):
            result.append((hwnd, title, cls))
    win32gui.EnumWindows(cb, None)
    return result

# Watch for Notice or file dialog for up to 15s
print("Watching for dialogs...")
file_dialog_opened = False
for i in range(30):
    time.sleep(0.5)

    # Check for Windows file dialog (#32770)
    file_dlgs = find_dialog_class('#32770')
    if file_dlgs:
        hwnd, title, cls = file_dlgs[0]
        print(f"File dialog: '{title}'")
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        print("File path submitted!")
        file_dialog_opened = True
        break

    # Check if Notice dialog appeared (look for "I agree" button via pyautogui image search or just click known position)
    # Notice is a Chrome overlay at center of page, "I agree" button at ~(944, 444) in viewport
    # In screen coords:
    notice_x = int(win_x + 944 * scale_x)
    notice_y = int(win_y + toolbar_h + 444 * scale_y)

    # Try to detect Notice by checking pixel (heuristic)
    if i == 4:  # After 2 seconds, try clicking "I agree"
        print(f"Trying 'I agree' click at ({notice_x}, {notice_y})")
        pyautogui.click(notice_x, notice_y)
        time.sleep(0.5)
        # Then click + again
        print(f"Re-clicking + at ({btn_x}, {btn_y})")
        pyautogui.click(btn_x, btn_y)

if not file_dialog_opened:
    print("File dialog not found, trying blind approach...")
    time.sleep(1)
    # Try directly clicking "+" again and handling any open dialog
    file_dlgs = find_dialog_class('#32770')
    if file_dlgs:
        hwnd, title, cls = file_dlgs[0]
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.3)
        pyautogui.press('enter')
        print("Blind submit done")

time.sleep(2)
print("Script done")
