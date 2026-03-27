# Talky — Implemented Features (Client + Server)

This document summarizes behavior shipped in the **main** branch (startup gate, remote Ollama fixes, recommended-model overrides, related server health) and **DMG 打包备忘** (updated **2026-03-27**). Use it as a checklist for **DMG / release** alignment and QA.

---

## 1. Startup & modes

| Area | Behavior |
|------|----------|
| **Local mode** | Does not start tray / hotkey / pipeline until Ollama preflight passes: reachable host, at least one model (via `/api/tags`). |
| **Cloud mode** | Does not start until `verify_cloud_server()` succeeds: `GET /api/health` with `status: ok`, non-empty `whisper_model` and `llm_model`, and valid `X-API-Key` when the server has keys configured. |
| **First-run wizard** | Full `OnboardingWizard`: local install vs **Connect remote**, remote host test, model selection, recommended model download hints. |
| **Returning users** | `QMessageBox` loops for not-running / no-model; **Quit** uses `NoRole` so primary action (re-check) appears first on macOS. |
| **Exit on failure** | Preflight failure → `main()` returns `1` (no half-started app). |

**Modules:** `main.py`, `talky/startup_gate.py`, `talky/onboarding.py`

---

## 2. Recommended Ollama model (no app rebuild to change)

| Mechanism | Details |
|-----------|---------|
| **Code default** | `talky/models.py` → `RECOMMENDED_OLLAMA_MODEL` |
| **Remote JSON** | Env `TALKY_RECOMMENDED_OLLAMA_JSON_URL` — fetched once per process (~8s timeout); merge over builtin. |
| **Local file** | `~/.talky/recommended_ollama.json` — wins over URL for any field it sets. |
| **Schema** | `model` / `model_name`, optional `library_url` / `ollama_library_url`, optional `pull_command` / `pull`. |
| **UI** | Wizard model page + returning-user “no model” dialog; optional **View on Ollama.com** when `library_url` is set. |
| **Defaults** | `AppSettings.ollama_model` default and settings UI empty fallback use `recommended_model_name()`. |

**Module:** `talky/recommended_ollama.py`

---

## 3. Ollama client (local & LAN)

| Issue fixed | Implementation |
|-------------|----------------|
| Global `ollama.chat()` ignored `OLLAMA_HOST` | `OllamaTextCleaner` uses `ollama.Client(host=OLLAMA_HOST)`; same for `check_ollama_reachable()` → `Client(host).list()`. |
| HTTP fallback | Unchanged: `_chat_via_http` for `/api/chat` when SDK still fails. |

**Modules:** `talky/llm_service.py`, `talky/permissions.py`

---

## 4. Paste & foreground

| Issue fixed | Implementation |
|-------------|----------------|
| Paste from worker thread failed on macOS | `paste_to_front_signal` + `QueuedConnection` → `_do_paste_to_front()` on Qt main thread. |

**Module:** `talky/controller.py`

---

## 5. Talky Cloud server (`talky-server`)

| Endpoint | Behavior |
|----------|----------|
| **`GET /api/health`** | If `api_keys.json` has entries → requires `X-API-Key`; returns `whisper_model` + `llm_model`; **503** `degraded` if either model string empty. |
| **`POST /api/process`** | Unchanged (audio → ASR → LLM). |

**Module:** `talky-server/main.py`

---

## 6. Cloud client verification

| Item | Details |
|------|---------|
| **`verify_cloud_server()`** | Validates health JSON and both model fields; used by startup gate and `CloudProcessService.health_check()`. |

**Module:** `talky/remote_service.py`

---

## 7. Known follow-ups (not blockers)

- **Wizard page 0 vs `NOT_RUNNING`:** If only the Ollama **CLI/app** is present but not running, the wizard may open on the “install Ollama” page instead of mode selection; workaround is uninstall CLI or use **Connect remote** from a clean `NOT_INSTALLED` path. (Optional code fix: always start mode selection on first run.)
- **DMG visual polish:** `TODO(DMG/visual)` in `talky/onboarding.py` — low-contrast `#555` helper text on dark sheets; align with final app stylesheet before signed release.

---

## 8. DMG build (separate worktree)

Packaging lives on branch **`feature/dmg-unsigned-prototype`** (git worktree: `.worktrees/feature-dmg-unsigned-prototype/`).

**Syncing client code from `main`:** A plain `git merge main` often conflicts (DMG `main.py` adds single-instance lock, `aboutToQuit` cleanup, debug log, mic timer, NSAppearance). A reliable approach:

1. Copy these paths from the **main repo** into the worktree (overwrite):  
   `talky/controller.py`, `talky/llm_service.py`, `talky/permissions.py`, `talky/remote_service.py`, `talky/models.py`, `talky/onboarding.py`, `talky/ui.py`, `talky/startup_gate.py`, `talky/recommended_ollama.py`, and the matching `tests/` files plus this `docs/FEATURES.md`.
2. **Merge manually** worktree `main.py`: keep DMG-only blocks (`fcntl` lock, `append_debug_log`, Foundation/AppKit, `_cleanup_on_quit`, mic `QTimer`) and insert **`startup_gate`** (`ensure_cloud_ready` / `ensure_local_ollama_ready`) **before** `AppController` is constructed, with **`return 1`** on failure; use **`QMessageBox.warning`** for accessibility (not tray) when the tray is not ready yet; **remove** the old inline onboarding block (wizard is inside `ensure_local_ollama_ready`).

**Build:**

From the **repository root** (or your DMG worktree checkout):

```bash
chmod +x scripts/build_unsigned_dmg.sh   # once, if needed
./scripts/build_unsigned_dmg.sh "0.4.0-local-gate.1"   # example version tag
```

Output: `release/Talky-<version>-unsigned.dmg`.

**Lightweight PyInstaller bundle:** The build script **does not** bundle **mlx**, **mlx_whisper**, **numpy**, or **torch** (and keeps **scipy** / **numba** / **llvmlite** excluded), keeping **`dist/Talky.app`** around ~100MB-class. **Local** ASR **lazy-imports** those libraries only when needed. For a **frozen** `.app` in local mode, either run from a **full dev venv** (`pip install -r requirements.txt`, `python download_model.py`, `python main.py`) or install once into **`~/.talky/extra-site-packages`** (see `talky/asr_service.py`: `pip install --target ~/.talky/extra-site-packages mlx mlx-whisper numpy`, then restart the app). **Cloud mode** needs no local MLX. Recording uses stdlib **`wave`** (no numpy on the capture path).

**`build_unsigned_dmg.sh` — default DMG flow**

1. PyInstaller produces `dist/Talky.app`; the script copies it (plus `Applications` symlink) into **`build/dmg_stage`**.
2. **By default**, the stage is **`ditto`**’d to **`/tmp/talky-hdiutil.*/dmg_stage`** so `hdiutil` sees an ASCII path (helps with Unicode or synced project locations).
3. One **`hdiutil create`** builds a compressed DMG:  
   `-volname "Talky" -srcfolder <dmg_stage> -ov -format UDZO` → temporary output, then **`mv`** into `release/`.
4. If direct **UDZO** fails, the script retries **UDRO** from the same folder + **`hdiutil convert`** to UDZO (still no blank-image attach/ditto pipeline).

**Build ID:** Each run stamps a random 6-character **`TalkyBuildId`** into the app `Info.plist` and **`CURRENT_BUILD_ID`** in `talky/version_checker.py` (staging script does not add a visible `BUILD.txt` on the DMG volume). Override: `TALKY_BUILD_ID_OVERRIDE=...`.

| Mode / variable | What it does |
|-----------------|--------------|
| **Default** | Single-step **`-srcfolder`** UDZO from `dmg_stage` (after `/tmp` copy unless skipped below). |
| **`TALKY_DMG_SKIP_TMP_HDIUTIL=1`** | Run `hdiutil` against **`build/dmg_stage` in the repo** (no `/tmp` copy). Use only if paths are plain ASCII and you want to debug; iCloud/sync paths may still be risky. |
| **`TALKY_HDIUTIL_VERBOSE=1`** | Pass **`-verbose`** to `hdiutil` / `convert`. |
| **`TALKY_DMG_FANCY=1`** | **UDRW** image from the same **`dmg_stage`** with volume name **`Talky Installer`** → mount → optional background + AppleScript icon layout → detach → **convert** to UDZO. Slower and more failure-prone, nicer Finder window. |

**If `hdiutil` hangs or times out (`Operation timed out`, long silence):**

- Large **`-srcfolder`** trees can still stress `hdiutil` on some macOS builds; watch **`hdiutil`** / **`diskimages-helper`** in Activity Monitor.
- After a successful PyInstaller step, **`dist/Talky.app`** is usually valid — zip or run locally while you retry DMG.
- Run the script in a normal local Terminal (not a short-timeout environment); pause heavy disk jobs (Time Machine, huge copies).
- Try **`TALKY_HDIUTIL_VERBOSE=1`**; optionally toggle **`TALKY_DMG_SKIP_TMP_HDIUTIL`** to see if `/tmp` vs repo path changes behavior.
- Manual **UDRO** (often faster than UDZO, larger file):  
  `hdiutil create -volname "Talky" -srcfolder build/dmg_stage -ov -format UDRO release/Talky-xxx-unsigned.dmg`
- Fallback distribution: **`ditto` + `zip`** for **`Talky.app.zip`**.

**Git：** worktree 上若曾 `git stash` 过「merge main 前」的改动，用 `git stash list` 查看；不需要时 `git stash drop`。

See also: `docs/DMG_LAN_OLLAMA.md` for Mac mini + MacBook Ollama host setup.
