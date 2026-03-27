# Onboarding Wizard Design

## Problem

DMG users who don't have Ollama installed get no guidance until their first recording fails — a 3-second tray notification that's easy to miss. First-time users need a clear setup flow.

## Design Decisions

| Decision | Choice |
|----------|--------|
| Trigger | Every startup checks; first-time users get full wizard, returning users get brief prompt |
| UI form | Wizard dialog (QDialog + QStackedWidget) |
| Detection | Auto-detect local install first, then ask user to choose local/remote |
| Recommended model | Single model, configurable via `RECOMMENDED_OLLAMA_MODEL` constant |
| Ollama install | Open browser to ollama.com, user installs manually, then "re-check" |
| Remote model selection | Fetch model list from remote `/api/tags`, user picks from dropdown |
| Language | Follow macOS system language (Chinese → Chinese UI, else English) |

## Startup Detection Flow

```
App startup
  │
  ├─ Cloud mode (settings.mode == "cloud") → skip, normal start
  │
  ├─ Check 3 conditions:
  │    ├─ is_ollama_installed()       (shutil.which)
  │    ├─ check_ollama_reachable()    (existing)
  │    └─ detect_ollama_model()       (existing)
  │
  ├─ All pass → normal start
  │
  ├─ Any fail + first-time user (no settings.json) → full OnboardingWizard
  │
  └─ Any fail + returning user → brief QMessageBox prompt (non-blocking)
```

## Wizard Pages

### Page 1: Welcome + Mode Selection

_Only shown when Ollama is not installed locally._

- Welcome message: "Talky needs Ollama to process voice text"
- Two option cards:
  - **Run locally** — "Install Ollama on this Mac"
  - **Connect remote** — "Use Ollama on another device in your LAN"

### Page 2a: Local Install Guide

- Instructions: "Please download and install Ollama first"
- "Go to Download" button → opens browser to `ollama.com/download`
- "I've installed, re-check" button → runs detection, auto-advances on success

### Page 2b: Remote Configuration

- Input field: Ollama address (placeholder: `http://192.168.1.x:11434`)
- "Test Connection" button → calls `/api/tags`
  - Success: show model dropdown for selection
  - Failure: show error, stay on page

### Page 3: Model Preparation

_Local path, after Ollama is installed._

- If models exist → dropdown to select, can proceed
- If no models → show recommended model (`RECOMMENDED_OLLAMA_MODEL`), terminal command `ollama pull <model>`, "Copy Command" button
- "I've downloaded, re-check" button → refreshes model list

### Page 4: Complete

- "All set! Hold the Fn key to start voice input"
- "Done" button → save settings, close wizard, normal start

## Returning User Prompts

Non-blocking QMessageBox for each failure case:

- **Not installed** → "Ollama not detected, please install and restart Talky" + "Go to Download"
- **Not running** → "Ollama is not running, please run `ollama serve`" + "OK"
- **No models** → "No models detected, please run `ollama pull <model>`" + "Copy Command"

User can dismiss and continue (e.g. Cloud mode users).

## Code Changes

### New files

- `talky/onboarding.py` — all wizard logic (detection functions + `OnboardingWizard` QDialog)

### Modified files

- `talky/models.py` — add `RECOMMENDED_OLLAMA_MODEL` constant; default `ollama_model` references it
- `main.py` — insert detection before `controller.start()`, trigger wizard or prompt
- `talky/permissions.py` — add `is_ollama_installed()` (via `shutil.which`)

### Unchanged files

- `talky/ui.py` — wizard is independent, no coupling
- `talky/controller.py` — unaware of wizard; reads config as before

## Data Flow

```
main.py
  │
  ├─ Run 3 detection checks
  │
  ├─ All pass → controller.start()
  │
  ├─ First-time → OnboardingWizard(config_store)
  │    └─ Wizard completes → writes settings.json → controller.start()
  │
  └─ Returning user → QMessageBox prompt
       └─ User dismisses → controller.start() (degraded)
```

Wizard writes directly to `config_store`; controller reads config on start. Zero intrusion to existing code.
