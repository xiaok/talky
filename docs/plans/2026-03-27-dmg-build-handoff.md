# DMG 未签名构建 — 状态记录（给新 session）

**日期**: 2026-03-27
**分支**: `feature/dmg-unsigned-prototype`
**常用工作副本**: 仓库内 git worktree `.worktrees/feature-dmg-unsigned-prototype`（与主目录 `main` 并行开发；DMG 相关提交多在此 worktree）。

---

## 0. 最新进展快照（本次会话收敛）

> 这一节用于"开新 session 快速接手"，优先看这里。

### 已验证通过（用户已确认）

1. **新 DMG 可安装并启动。**
2. **不 reset 的情况下，按住 fn 可以识别出文字。**
3. **onboarding 选择 remote 且连接通过后，settings 持久保存为 `mode=remote`。**
4. **Reset → onboarding → whisper 模型下载 → 自动重启后 tray icon 正常显示。**（本次会话修复）

### 本次已修复（代码层面）

1. **Whisper 下载后自动准备运行环境**
   - `Download Model (~3 GB)` 点击后，除下载模型外会自动安装运行库。
   - 进度文案增加 `Preparing runtime environment...`。
2. **本地 ASR 去除 ffmpeg 依赖**
   - `asr_service.transcribe()` 改为先读取 wav 为 float32 波形再调用 `mlx_whisper`。
3. **remote/local 模式语义**
   - 新增 `mode=remote` 语义（与 `local/cloud` 并列）。
   - settings 内切换 `local/remote` 时，必须先验证 host/model 可用才允许保存；失败回滚到上次可用配置。
4. **错误自动记录**
   - 自动写入 `~/.talky/logs/error-msg.md`（含版本号、包名、错误内容、关键 settings）。
5. **Tray icon 在自动重启后消失（已修复）**
   - **根因**：`os.execv` 做同 PID 进程替换，macOS WindowServer 不会为同一 PID 重新注册 `NSStatusItem`。
   - **修复**：bundled `.app` 重启改用 `open` 走 LaunchServices，旧进程完全退出后以全新 PID 启动（`sleep 0.5; open /path/to/Talky.app`）。
   - 增加 `_verify_tray_visible()` 延迟检查，200ms 后若 tray 仍不可见则自动重试。
   - 重启失败时恢复 tray 可见并弹窗提示手动重启，不再出现"只消失不重启"。
   - 重启命令过滤 macOS 启动参数 `-psn_*`。
   - 新增测试文件 `tests/test_ui_restart.py`。

### 仍在观察/待复测

1. ~~**Tray icon 有时不可见（间歇性）**~~ → **已修复**（见上方第 5 项），重启场景下的 tray 消失问题已定位到根因并解决。偶发不可见（非重启场景）暂未复现，继续观察。
2. **运行库自动安装对系统 Python 的依赖**
   - 当前策略：自动寻找与 app Python ABI 匹配的解释器（3.12），并安装到 `~/.talky/extra-site-packages`；
   - 对"机器完全无 Python"的场景目前仍是失败提示，尚未实现"自动下载/内置 Python runtime"。

### 近期高频报错与根因（已定位）

1. `module 'mlx.core' has no attribute 'array'`
   - 根因：装进了不匹配 ABI 的扩展（如 `core.cpython-39-*.so`，但 app 是 py3.12）。
   - 现有修复：安装器要求主次版本匹配，并在重装前清理不兼容 `mlx/mlx_whisper` 残留目录。
2. `Processing failed: [Errno 2] No such file or directory: 'ffmpeg'`
   - 根因：把音频路径直接传给 `mlx_whisper` 触发 ffmpeg 依赖。
   - 现有修复：改为传入内存波形数组。

### 新 session 建议起手验证（按顺序）

1. 清理旧 app，安装新 DMG。
2. 走一次 reset + onboarding remote 流程，确认：
   - `settings.json` 最终为 `mode=remote`
   - 模型下载 + runtime 准备后可直接识别
   - **tray icon 在重启后正常出现**
3. 观察 tray icon 是否稳定显示（首次启动、重启后、授权弹窗后）。
4. 若失败，优先收集：
   - `~/.talky/logs/error-msg.md`
   - `~/.talky/logs/debug.log`（现包含 `TrayApp.show()` / `_verify_tray_visible()` / `Restart requested` 诊断行）
   - `~/Library/Logs/DiagnosticReports/Talky-*.ips`

---

## 1. 当前遇到的问题（现象）

1. **`hdiutil create -srcfolder` + 大体积 `.app`**
   容易触发 **内部超时或极久无响应**（大目录树一次性打包进 DMG）。

2. **空白整卷镜像（dense UDIF）**
   在部分 **macOS 版本/测试版** 上，`hdiutil create` 阶段表现为 **Activity Monitor 里几乎 0 CPU、0 写入**，像挂住而非正常写盘。

3. **`hdiutil` 与路径**
   非 ASCII 路径、同步盘（iCloud/Dropbox 等）曾加剧不稳定；脚本已默认把 stage 拷到 **`/tmp` 下 ASCII 路径** 再跑 `hdiutil`。

4. **体积对比易误解**
   `du` 的 `.app` 为未压缩体积；**压缩后 DMG/ZIP** 数字更小，不能直接对比「以前 108MB 笔记」与「现在 dist 二百多 MB」。

5. **Shell / git**
   zsh 若未开 `interactivecomments`，**同一行里 `git … # 注释`** 会把 `#` 交给 git，报 `ambiguous argument '#'`。构建说明里已强调：**一行一条命令**，注释单独一行。

6. **`release/`**
   若构建中断或仅跑到某步，目录里可能只有 `RELEASE_NOTES.md` 等，**没有最终 `.dmg`**。

---

## 2. 已实现的能力（脚本 + 产物）

**脚本**: `.worktrees/feature-dmg-unsigned-prototype/scripts/build_unsigned_dmg.sh`（主仓库合并前以 worktree 为准）。

| 能力 | 说明 |
|------|------|
| **默认 DMG 路径** | **空白可写卷 → `ditto` 拷贝 stage → `hdiutil convert` → UDZO**，避开默认对大树的 `create -srcfolder`。 |
| **SPARSE 默认**（`314c078`） | 空白卷优先 **`-type SPARSE`**（`…-rw-fill.sparseimage`），减少 dense UDIF 预分配导致的 **0 写入/卡住**；失败或显式关闭时回退 **UDIF `.dmg`**。 |
| **macOS 新规则** | 空白镜像用 **`-type UDIF`**，避免仅 `-format UDRW` 且无 `srcfolder` 时被拒（`1993bba`）。 |
| **`/tmp` 工作区** | 默认 `ditto` stage 到 `/tmp/talky-hdiutil.*`，最终 DMG 再 `mv` 到 `release/`。 |
| **回退链** | 默认 ditto 路径失败后再试 **`create -srcfolder` UDZO → UDRO + convert** 等（见 `hdiutil_make_udzo`）。 |
| **可选「慢路径」** | `TALKY_DMG_FANCY=1`：RW 镜像 + 挂载 + Finder 布局 + convert（脚本内原有说明）。 |
| **PyInstaller** | 修正 plist / `PlistBuddy` 噪声；**不要**使用无效的 `--hidden-import pyobjc-framework-AVFoundation`，保留 **`AVFoundation`**。 |
| **签名** | ad-hoc `codesign` + 麦克风 entitlement；校验 `Identifier`。 |

**应用行为（与 `main` 对齐的合并项，在 feature 分支 / worktree）**
启动前 **`ensure_cloud_ready` / `ensure_local_ollama_ready`**、`startup_gate`、`recommended_ollama`、controller/llm/onboarding/remote/models/permissions/ui 等与 DMG 打包目标相关的逻辑已按此前计划从 `main` 同步；**`main.py`** 在 DMG 分支上保留 fcntl 锁、调试日志、AppKit/Foundation、mic timer、`_cleanup_on_quit` 等 DMG/桌面侧细节（以 worktree 实际文件为准）。

---

## 3. 环境变量（调试 / 覆盖）

| 变量 | 作用 |
|------|------|
| `TALKY_DMG_SKIP_TMP_HDIUTIL=1` | 不在 `/tmp` 复制 stage，直接在 `STAGE_DIR` 上跑 `hdiutil`（仅当路径干净、需排查时）。 |
| `TALKY_HDIUTIL_VERBOSE=1` | 给 `hdiutil` 加 `-verbose`。 |
| `TALKY_DMG_TRY_SRCFOLDER_FIRST=1` | 先尝试 `create -srcfolder`（在能成功时可能更快）。 |
| `TALKY_DMG_BLANK_UDIF=1` | **跳过 SPARSE**，空白卷只用 dense **UDIF**（兼容/对照用）。 |
| `TALKY_DMG_FANCY=1` | Finder 布局慢路径。 |

---

## 4. 卡点与待验证（新 session 优先做）

1. **SPARSE 路径是否在用户当前 macOS 上稳定**
   已提交 `314c078`，需在真实机器上 **完整跑通** `./scripts/build_unsigned_dmg.sh "<version>"`，确认不再长时间卡在 `hdiutil create`。

2. **若仍卡住**
   收集：**最后一条脚本输出**、`TALKY_HDIUTIL_VERBOSE=1` 日志、Activity Monitor 中 **`hdiutil` / `diskimages-helper`**、macOS 版本（是否测试版）。必要时对比 **`TALKY_DMG_BLANK_UDIF=1`** 与 SPARSE 行为。

3. **迭代速度（未实现）**
   可选：`TALKY_DMG_DMG_ONLY` 或「若 `dist/Talky.app` 已存在则跳过 PyInstaller」——**尚未加**；仅在 DMG 流程稳定后、需要频繁打 DMG 时再考虑。

4. **远程同步**
   若 `origin` 落后本地 commits，需 **push** `feature/dmg-unsigned-prototype`（以用户策略为准）。

---

## 5. 相关提交（worktree 上示例）

```
314c078 build(dmg): default blank volume to SPARSE before UDIF
d0c8c48 chore(dmg): log before hdiutil create/attach (long silent phases)
ffd7f56 docs(dmg): clarify zsh # vs git; progress lines for ditto/convert
1993bba fix(dmg): blank image use -type UDIF (macOS 26 hdiutil -format rule)
851a23d fix(dmg): default blank-RW+ditto DMG; fix PyInstaller plist noise
```

---

## 6. 新 session 一句话目标

在 **当前 macOS** 上 **可靠、可重复** 产出 `release/Talky-<version>-unsigned.dmg`；默认依赖 **SPARSE 空白卷 + ditto + UDZO**，并保留 **UDIF / srcfolder** 作为回退与对照。
