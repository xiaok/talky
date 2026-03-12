# Talky

![Talky Banner](assets/github-banner.png)
![Talky Launcher Logo](assets/talky-launcher-logo.png)

Talky is a local-first voice input assistant optimized for macOS (Apple Silicon).  
It captures voice with a hold-to-talk workflow, runs ASR + LLM locally, and outputs polished text into the active app.

## Vision

**Language:** [English](#vision-en) | [中文](#vision-cn)

### Vision En

#### Why Talky?

Ideas often move faster than our fingers can type.

While there are many excellent voice input tools available, we have always craved a purer, more private, and highly controllable local solution for our high-frequency daily coding and writing. Cloud-based products raise privacy concerns, and native local dictation often results in raw text filled with filler words ("um", "uh") that take more time to edit than type.

Talky is not trying to reinvent the wheel. It aims to seamlessly stitch powerful open-source AI models (ASR + LLM) into the daily macOS workflow, serving as a quiet, private, and understanding local assistant.

### 🛡️ Privacy First

Your inspiration belongs to you. Talky's entire workflow relies purely on your device's compute. No cloud APIs, no subscriptions, no data uploads, letting you record with peace of mind in any network environment.

### 🧠 Speech-to-Intent

Standing on the shoulders of giants, Talky does not just "listen" - it helps you "think" using local LLMs (like Qwen). It silently cleans up filler words, corrects grammar, and structures logic in the background, striving to paste clean, decent, and ready-to-use text.

### ⚡ Seamless Hold-to-Talk

Returning to the most natural "hold to speak, release to process" logic. The generated result is accurately and automatically pasted into your currently focused editor or chat window. Lost focus accidentally? Talky gracefully summons a floating copy panel to ensure not a single word you say goes to waste.

### 📝 Silent Archiving

Every flash of thought has value. Talky automatically appends all generated text to a daily-archived local Markdown file (`history/YYYY-MM-DD.md`). It is not just a cross-app input "peripheral", but also a convenient daily memo for your thoughts.

Talky is simply a starting point for exploring the potential of local AI, dedicated to making the journey from "thought" to "expression" just a little bit smoother.

### Vision Cn

#### 为什么做 Talky？

我们的想法总是比敲击键盘的手指快。

市面上已经有许多优秀的语音输入工具，但在日常高频的开发和写作中，我们始终渴望一个更纯粹、更私密、且高度可控的本地化方案。云端产品让人担忧数据隐私，而原生的本地听写又往往充斥着无意义的口语瑕疵，后期修改成本极高。

Talky 并非想要重新发明轮子，而是致力于将强大的开源 AI 模型（ASR + LLM）无缝缝合进 macOS 的日常输入流中，做一个安静、私密且懂你的本地辅助工具。

### 🛡️ 本地与隐私优先

你的灵感属于你自己。Talky 的整个工作流完全依赖你设备上的算力运行。没有云端 API，没有订阅，没有数据上传，让你在任何网络环境下都能安心记录。

### 🧠 意图级的文本梳理

Talky 站在巨人的肩膀上，不仅负责“听”，更借助本地大模型（如 Qwen 等）帮你“想”。它会在后台静默清理冗余的语气词、修正语法并梳理逻辑，力求在粘贴时提供一份干净、得体、直接可用的文本。

### ⚡ 极简的交互直觉

回归最自然的“按住说话，松开处理”逻辑。生成的结果会自动精准粘贴到你当前聚焦的编辑器或聊天窗口。如果不小心切走了焦点？Talky 会贴心地唤起一个悬浮复制面板，确保你的任何一次发音都不会白费。

### 📝 静默的历史归档

每一次闪现的想法都有其价值。Talky 会将所有生成的文本自动追加到按天归档的本地 Markdown 文件中（`history/YYYY-MM-DD.md`）。它不仅是一个跨应用的输入“外设”，也顺便成了你每日思考的备忘录。

Talky 只是一个探索本地 AI 潜力的起点，致力于让“思考”到“表达”的过程，再顺畅那么一点点。

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
