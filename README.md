# Talky

![Talky Banner](assets/github-banner.png)

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
