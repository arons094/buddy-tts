# buddy-tts

```
  ╭─────────────────────────────────╮
  │  *honks in text-to-speech*      │
  ╰─────────────────────────────────╯
        \
         \      ___
          \    [___]
           \    (@>>    <-- talking!
                 ||
               _(__)_
                ^^^^
               Trellis
```

Gives your Claude Code companion a voice. Monitors the terminal for speech bubbles and reads them aloud using either macOS built-in TTS or a custom [Fish.audio](https://fish.audio) voice.

> **macOS only.** Requires accessibility permissions to read terminal content.

---

## How it works

### The problem

Claude Code's companion (mine is Trellis the goose) renders speech bubbles directly in the terminal UI. This is pure client-side rendering — the text never passes through Claude Code's hooks system, so there's no built-in way to intercept it.

### The solution: macOS Accessibility API

macOS exposes a system-wide [Accessibility API](https://developer.apple.com/documentation/applicationservices/axuielement_h) (`AXUIElement`) that allows any trusted application to read the content of UI elements in other apps — including terminal text. This is the same API used by screen readers like VoiceOver.

buddy-tts uses this API to poll the terminal window content and detect when the companion speaks.

### Step-by-step flow

```
┌─────────────────────────────────────────────────────────┐
│  Every 0.3s                                             │
│                                                         │
│  1. NSWorkspace → find Terminal or iTerm2 process       │
│  2. AXUIElement → get all AXWindows                     │
│  3. Recurse AXChildren tree → collect all AXTextAreas   │
│  4. Join text → scan for (@>> (goose talking beak)      │
│  5. If beak found → extract speech bubble text          │
│  6. If new text → send to TTS engine                    │
└─────────────────────────────────────────────────────────┘
```

### Accessibility tree traversal

The terminal is represented as a tree of `AXUIElement` nodes. buddy-tts walks this tree recursively looking for nodes with `AXRole = AXTextArea`, which is where terminal content lives:

```
AXApplication (Terminal)
└── AXWindow
    └── AXSplitGroup
        └── AXScrollArea
            └── AXTextArea  ← full terminal content as a string
```

Each `AXTextArea` value contains the entire visible text of that terminal pane, including the companion's goose art and speech bubble rendered as Unicode box-drawing characters.

### Detecting speech

The companion renders two states:

```
Silent goose:          Talking goose:
  [___]                  [___]
   (=>>                   (@>>   ← beak changes from = to @
    ||                     ||
  _(__)_                _(__)_
```

buddy-tts watches for the transition from no `(@>>` to `(@>>` present in the terminal text. This rising edge triggers bubble extraction — reading on every poll while talking would repeat the same text.

**NOTE** Your companion will be different, you may need to update the code on how to check for when it is speaking.
### Extracting bubble text

When the talking beak is detected, the script searches within ±15 lines of the goose for a Unicode box:

```
╭────────────────────────────────╮
│ Some witty remark from Trellis │    [___]
│ goes here across multiple      │      (@>>
│ lines if needed                │─     ||
╰────────────────────────────────╯   _(__)_
```

It finds the top border (`╭─...─╮`), the bottom border (`╰─...─╯`), then strips the `│ ... │` delimiters from each inner line and joins them into a single string for the TTS engine.

---

## Installation

### Prerequisites

- macOS (Accessibility API is macOS-only)
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for package management

Install uv if you don't have it:

```bash
brew install uv
```

### Setup

```bash
# 1. Clone the repo
git clone <repo-url> ~/.buddy-tts
cd ~/.buddy-tts

# 2. Install dependencies
uv sync

# 3. Configure
cp .env.example .env
# Edit .env with your preferred TTS engine (see Configuration below)
```

Or just run the setup script which does all of the above:

```bash
bash setup.sh
```

### Accessibility permission

The script needs permission to read other apps' UI content. Grant it once in:

**System Settings → Privacy & Security → Accessibility**

Enable your terminal app (Terminal.app or iTerm2).

### Auto-start with Claude Code

To have buddy-tts launch automatically every time you open Claude Code, add a `SessionStart` hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "pkill -f buddy_tts.py 2>/dev/null; uv run --project ~/.buddy-tts python ~/.buddy-tts/buddy_tts.py >> /tmp/buddy-tts.log 2>&1 &",
        "async": true
      }]
    }]
  }
}
```

The `pkill` guard ensures only one instance runs if you open multiple Claude Code windows.

### Run manually

```bash
uv run python buddy_tts.py
```

Logs (when running via hook) go to `/tmp/buddy-tts.log`.

---

## Configuration

Copy `.env.example` to `.env` and edit it:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `TTS_ENGINE` | `macos` | `macos` for built-in `say`, or `fish` for Fish.audio |
| `MACOS_VOICE` | _(system default)_ | macOS voice name, e.g. `Samantha`. Run `say -v '?'` to list all. |
| `FISH_API_KEY` | — | Your Fish.audio API key |
| `FISH_VOICE_ID` | — | Voice model reference ID from Fish.audio |
| `POLL_INTERVAL` | `0.3` | How often (in seconds) to check the terminal |

### Option A: macOS built-in TTS (no account needed)

```ini
TTS_ENGINE=macos
MACOS_VOICE=Samantha
```

List available voices:
```bash
say -v '?'
```

### Option B: Fish.audio custom voice

```ini
TTS_ENGINE=fish
FISH_API_KEY=your_key_here
FISH_VOICE_ID=your_voice_model_id_here
```

Sign up and get an API key at [fish.audio](https://fish.audio). The `FISH_VOICE_ID` is the `reference_id` shown on any voice model's page. If Fish.audio returns an error (e.g. out of credits), it automatically falls back to macOS `say`.

---

## Troubleshooting

**No speech / nothing happens**
- Check `/tmp/buddy-tts.log` for errors
- Confirm accessibility permission is granted for your terminal app
- Make sure Claude Code is running in Terminal.app or iTerm2 (other terminals are not yet supported)

**Fish.audio not working**
- Verify your API key and voice ID in `.env`
- Check your Fish.audio account balance — the API returns HTTP 402 when out of credits
- The script will fall back to `say` automatically on any Fish.audio error

**Duplicate speech / speaking twice**
- The `pkill` in the hook command prevents this — only one instance runs at a time. If you started it manually _and_ via hook, kill the extra: `pkill -f buddy_tts.py`
