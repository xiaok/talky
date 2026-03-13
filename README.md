# Talky

![Talky Banner](assets/github-banner.png)

Talky is a local-first voice input assistant optimized for macOS (Apple Silicon).  
It captures voice with a hold-to-talk workflow, runs ASR + LLM locally, and outputs polished text into the active app.

**Language:** English | [中文](README.zh.md)

### 1) Product Highlights and Core Flow

**Highlights**
- Local-first pipeline: ASR + LLM runs on your machine.
- Hold-to-talk interaction: press, speak, release, paste.
- Smart fallback: if no valid focus target, show floating copy panel.
- Daily local archive: `history/YYYY-MM-DD.md`.

**Core operation flow**
1. Hold hotkey to record.
2. Release to transcribe (ASR).
3. Clean text with local LLM.
4. Auto-paste to focused app (or copy panel fallback).

### 2) Pre-Install Checklist

Make sure these are ready before first run:

- `python3 --version` works
- `ollama --version` works
- `ollama list` shows at least one local model
- >= 10 GB free disk space
- Network can reach PyPI + Hugging Face
- (Some machines) `ffmpeg` installed for audio decoding compatibility
- Optional acceleration:
  ```bash
  export HF_TOKEN=your_token_here
  ```

One-command preflight:

```bash
python3 --version && ollama --version && ollama list && \
echo "Disk free:" && df -h .
```

If no model is installed:

```bash
ollama pull <your-model>
```

### 3) First Install and Daily Usage (Step-by-step CLI)

Install prerequisites manually first:
- Python 3
- Ollama: https://ollama.com/download

#### Step A (one-time): system dependency setup

Install Homebrew first (if not installed), then install ffmpeg.

If you use a local proxy, first confirm your own proxy port. The commands below use `7897` as an example:

```bash
export https_proxy=http://127.0.0.1:7897
export http_proxy=http://127.0.0.1:7897
brew install ffmpeg
```

#### Step B (one-time): environment fix + model download

```bash
cd /path/to/talky
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you use SOCKS proxy and see `socksio` / proxy errors:

```bash
pip install "httpx[socks]"
```

If you use proxy-based model download, configure it before downloading:

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_TOKEN=your_token_here
export all_proxy=socks5://127.0.0.1:7897
python3 download_model.py
```

#### Step C (daily): one-click start

```bash
cd /path/to/talky
chmod +x start_talky.command
./start_talky.command
```

Then grant macOS permissions:
- `System Settings -> Privacy & Security -> Microphone`
- `System Settings -> Privacy & Security -> Accessibility`

After startup:
1. Hold hotkey to speak.
2. Release to process.
3. Confirm text is pasted.

Notes:
- No need to run `chmod +x` again.
- Startup checks remote git updates and fast-forwards when available.
- `start_talky.command` unsets proxy variables before app launch to keep local Ollama access stable.
- If your network requires proxy for model download, run `download_model.py` manually (Step B) before daily start.

#### Quick troubleshooting

If Whisper model is broken/incomplete:

```bash
rm -rf local_whisper_model
source .venv/bin/activate
python download_model.py
./start_talky.command
```

If Ollama warm-up returns `502`:

```bash
pkill ollama
ollama serve
```

### 4) Vision

Talky aims to make voice input truly usable for daily coding and writing:
- private (local compute, no cloud upload)
- clean (remove filler and polish wording)
- practical (works across apps with minimal friction)

It is a focused, local assistant that helps you move from thought to text faster.
