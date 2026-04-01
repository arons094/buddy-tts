#!/bin/bash
# Buddy TTS setup script — run once to install dependencies and configure.
set -e

BUDDY_DIR="$HOME/.buddy-tts"

echo "=== Buddy TTS Setup ==="

# 1. Check for uv
if ! command -v uv &>/dev/null; then
    echo "→ uv not found. Install it first:"
    echo "    brew install uv"
    echo "  or visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# 2. Install dependencies
echo "→ Installing dependencies with uv..."
uv sync --project "$BUDDY_DIR"

# 3. Create .env from example if not already present
if [ ! -f "$BUDDY_DIR/.env" ]; then
    cp "$BUDDY_DIR/.env.example" "$BUDDY_DIR/.env"
    echo "→ Created $BUDDY_DIR/.env — edit it to configure your TTS engine."
else
    echo "→ $BUDDY_DIR/.env already exists, skipping."
fi

# 4. Accessibility permission reminder
echo ""
echo "⚠  Accessibility permission required:"
echo "   System Settings → Privacy & Security → Accessibility"
echo "   Enable your terminal app (Terminal or iTerm2)."
echo ""

# 5. Claude Code hook instructions
HOOK_CMD="pkill -f buddy_tts.py 2>/dev/null; uv run --project $BUDDY_DIR python $BUDDY_DIR/buddy_tts.py >> /tmp/buddy-tts.log 2>&1 &"

if [ -f "$HOME/.claude/settings.json" ] && grep -q "buddy_tts" "$HOME/.claude/settings.json" 2>/dev/null; then
    echo "→ Claude Code hook already present in ~/.claude/settings.json."
else
    echo "To auto-start on Claude Code launch, add this to ~/.claude/settings.json:"
    echo ""
    echo '  "hooks": {'
    echo '    "SessionStart": [{'
    echo '      "hooks": [{'
    echo '        "type": "command",'
    echo "        \"command\": \"$HOOK_CMD\","
    echo '        "async": true'
    echo '      }]'
    echo '    }]'
    echo '  }'
fi

echo ""
echo "=== Setup complete ==="
echo "Run manually: uv run --project $BUDDY_DIR python $BUDDY_DIR/buddy_tts.py"
