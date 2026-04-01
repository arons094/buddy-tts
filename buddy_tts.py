"""
Buddy TTS — monitors the Terminal accessibility tree for companion speech
bubbles and reads them aloud using either macOS `say` or Fish.audio TTS.

Configuration via ~/.buddy-tts/.env (copy .env.example to .env to get started).
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    kAXErrorSuccess,
)
import Cocoa

# ── Load .env ────────────────────────────────────────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── Config ───────────────────────────────────────────────────────────────────
TTS_ENGINE    = os.environ.get("TTS_ENGINE", "macos").lower()   # "macos" | "fish"
MACOS_VOICE   = os.environ.get("MACOS_VOICE", "")               # e.g. "Samantha"; blank = system default
FISH_API_KEY  = os.environ.get("FISH_API_KEY", "")
FISH_VOICE_ID = os.environ.get("FISH_VOICE_ID", "")
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "0.3"))

# ── Accessibility helpers ─────────────────────────────────────────────────────

def ax_get(element, attr):
    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    return value if err == kAXErrorSuccess else None


def find_text_areas(element, depth=0, max_depth=8, seen=None):
    if seen is None:
        seen = set()
    if depth > max_depth:
        return []
    try:
        eid = id(element)
        if eid in seen:
            return []
        seen.add(eid)
    except Exception:
        return []
    results = []
    if (ax_get(element, "AXRole") or "") == "AXTextArea":
        val = ax_get(element, "AXValue") or ""
        results.append(str(val))
    for child in (ax_get(element, "AXChildren") or []):
        results.extend(find_text_areas(child, depth + 1, max_depth, seen))
    return results


def get_terminal_ax():
    ws = Cocoa.NSWorkspace.sharedWorkspace()
    # Support Terminal and iTerm2
    for name in ("Terminal", "iTerm2"):
        app = next((a for a in ws.runningApplications() if a.localizedName() == name), None)
        if app:
            return AXUIElementCreateApplication(app.processIdentifier())
    return None


def get_combined_text(ax_app):
    windows = ax_get(ax_app, "AXWindows") or []
    texts = []
    for win in windows:
        texts.extend(find_text_areas(win))
    return "\n".join(texts)

# ── Bubble extraction ─────────────────────────────────────────────────────────

def extract_bubble_text(screen_text):
    """
    Finds any speech bubble in the terminal text by looking for a Unicode box:

        ╭────────────────────╮
        │ bubble text here   │
        ╰────────────────────╯
    """
    lines = screen_text.split("\n")

    top = next((i for i, l in enumerate(lines) if re.search(r'╭─+╮\s*$', l)), None)
    if top is None:
        return None
    bot = next((i for i, l in enumerate(lines) if i > top and re.search(r'╰─+╯', l)), None)
    if bot is None:
        return None

    text_lines = []
    for line in lines[top + 1:bot]:
        m = re.search(r'│ (.*?) *│', line)
        if m:
            text_lines.append(m.group(1).rstrip())

    return " ".join(t for t in text_lines if t).strip() or None

# ── TTS ───────────────────────────────────────────────────────────────────────

def speak_macos(text):
    cmd = ["say"]
    if MACOS_VOICE:
        cmd += ["-v", MACOS_VOICE]
    cmd.append(text)
    subprocess.Popen(cmd)


def speak_fish(text):
    import io
    from fish_audio_sdk import Session, TTSRequest
    import sounddevice as sd
    import soundfile as sf
    session = Session(FISH_API_KEY)
    audio_bytes = b"".join(session.tts(TTSRequest(reference_id=FISH_VOICE_ID, text=text)))
    data, samplerate = sf.read(io.BytesIO(audio_bytes))
    sd.play(data, samplerate)
    sd.wait()


def speak(text):
    print(f"[buddy says]: {text}")
    if TTS_ENGINE == "fish":
        if not FISH_API_KEY or not FISH_VOICE_ID:
            print("ERROR: TTS_ENGINE=fish but FISH_API_KEY or FISH_VOICE_ID not set in .env",
                  file=sys.stderr)
            return
        try:
            speak_fish(text)
            return
        except Exception as e:
            print(f"Fish.audio error: {e} — falling back to macOS say", file=sys.stderr)
    speak_macos(text)

# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    print(f"Buddy TTS starting (engine={TTS_ENGINE})")

    ax_app = get_terminal_ax()
    if not ax_app:
        print("No supported terminal found (Terminal or iTerm2)", file=sys.stderr)
        sys.exit(1)

    last_spoken = None

    print("Listening for speech bubbles...")

    while True:
        try:
            text = get_combined_text(ax_app)
            bubble = extract_bubble_text(text)
            if bubble and bubble != last_spoken:
                speak(bubble)
                last_spoken = bubble

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
