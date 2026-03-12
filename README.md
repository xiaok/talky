# Talky

![Talky Banner](assets/github-banner.png)
![Talky Launcher Logo](assets/talky-launcher-logo.png)

Talky is a local-first voice input assistant optimized for macOS (Apple Silicon).  
It captures voice with a hold-to-talk workflow, runs ASR + LLM locally, and outputs polished text into the active app.

## Core Flow

1. Hold hotkey to record
2. Release to transcribe (ASR)
3. Clean and structure text (LLM)
4. Paste to focus target, or show floating copy panel if no focus is available

## History Logging

Every generated output is appended to a daily markdown file:

- `history/YYYY-MM-DD.md`

## One-Click Start on macOS

Use `start_talky.command` in the project root to start Talky with one action.

What it does:
- Creates `.venv` if missing
- Installs dependencies from `requirements.txt`
- Downloads `local_whisper_model` if missing
- Starts `ollama serve` if needed
- Pulls the configured Ollama model from `~/.talky/settings.json` (fallback: `qwen3.5:9b`)
- Launches `main.py`

First-time setup:
```bash
chmod +x start_talky.command
```

Then start Talky:
- Double-click `start_talky.command` in Finder, or
- Run `./start_talky.command` in Terminal

### Optional: Dock launcher (.app)

For a better one-click experience, wrap the script as `Talky Launcher.app`
with Script Editor / Automator, then pin it to Dock and apply a custom icon.
