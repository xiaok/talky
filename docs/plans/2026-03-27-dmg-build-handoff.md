# DMG 未签名构建 — 状态记录（给新 session）

**日期**: 2026-03-27
**分支**: `main`（所有 worktree / feature 分支的代码已合并回 main）
**最新提交**: `faab99b fix(tray): use LaunchServices restart to fix tray icon missing after relaunch`

---

## 0. 最新进展快照（本次会话收敛）

> 这一节用于"开新 session 快速接手"，优先看这里。

### 当前状态一句话

**所有功能代码已合并到 `main`，包括 4-tab Dashboard UI 大合并。但有 19 个文件未提交。需要重新打 DMG 验证。**

### 已验证通过（用户已确认）

1. **新 DMG 可安装并启动。**
2. **不 reset 的情况下，按住 fn 可以识别出文字。**
3. **onboarding 选择 remote 且连接通过后，settings 持久保存为 `mode=remote`。**
4. **Reset → onboarding → whisper 模型下载 → 自动重启后 tray icon 正常显示。**
5. **老用户流程 + 新用户流程均可跑通。**

> 注意：以上验证基于 UI 合并前的 DMG。UI 合并后尚未重新打包测试。

### 本会话最后完成的工作：UI 大合并

`talky/ui.py` 从 486 行的单页 SettingsWindow 恢复为 **2281 行的 4-tab Dashboard**：

| Tab | 类 | 功能 |
|-----|-----|------|
| Home | `HomeTab` | Logo、版本号、Fn/快捷键提示（Keycap 徽章）、GitHub Star、更新横幅 |
| History | `HistoryTab` | 左栏日期 + 右栏聊天气泡历史 |
| Dictionary | `DictionaryTab` | 3 列词卡网格、hover Edit/Delete、弹窗编辑 |
| Configs | `ConfigsTab` | Radio 热键组、Local/Remote/Cloud 模式、动态字段、Save + Reset |

样式从 `IOS26_STYLESHEET` 切换为 `NATIVE_STYLESHEET`（macOS 原生风格）。`IOS26_STYLESHEET` 保留为别名，`onboarding.py` / `startup_gate.py` 引用不受影响。

配套改动：
- `talky/history_store.py` — 新增 `list_dates()`, `read_entries()`
- `talky/controller.py` — 新增 `update_dictionary()`

### 历次已修复的问题

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | Tray icon 重启后消失 | `os.execv` 同 PID，macOS 不重新注册 NSStatusItem | `open` via LaunchServices 全新 PID |
| 2 | Whisper 依赖 ffmpeg | 音频路径直传 mlx_whisper | 改传内存 float32 波形 |
| 3 | `mlx.core` 无 `array` 属性 | ABI 不匹配的扩展 | 安装器要求版本匹配 + 清理残留 |
| 4 | remote 模式不持久 | 无 mode 字段 | 新增 `mode=remote` 语义 |
| 5 | 错误无记录 | 无 | 自动写入 `~/.talky/logs/error-msg.md` |

### 仍在观察

1. **Tray icon 偶发不可见（非重启场景）** — 重启场景已修复，偶发情况暂未复现
2. **运行库自动安装对系统 Python 的依赖** — 无 Python 的机器仍只有失败提示，未实现内置 runtime

---

## 1. 新 session 建议起手（按优先级）

### P0 — 验证 UI 合并后的 DMG

1. **先 source 运行验证**: `python3 main.py`，确认 4-tab Dashboard 正常
   - Home / History / Dictionary / Configs 四个 tab 都能切换和展示
   - Configs tab 的 Save / Reset / 模式切换正常工作
2. **提交当前改动**: 19 个未提交文件需要 commit
3. **重新打 DMG**: `./scripts/build_unsigned_dmg.sh "test"`
4. **安装后走完整流程**: reset → onboarding → 重启 → 确认 tray + Dashboard 正常

### P1 — UI 打磨

1. **Onboarding 视觉一致性**: `onboarding.py` / `startup_gate.py` 使用 `IOS26_STYLESHEET` 别名（指向 NATIVE），部分 objectName 可能视觉不对齐
2. **i18n 补全**: `_ZH` 字典 78 key，但部分 HomeTab 文案仍硬编码英文
3. **ConfigsTab 字段完整性**: 确认 `collect_settings()` 的输出都能被 `AppSettings` 接受

### P2 — 质量

1. 跑全部测试 `python3 -m pytest tests/`
2. 更新 `docs/FEATURES.md` 反映 4-tab UI

---

## 2. DMG 构建能力（脚本 + 产物）

**脚本**: `scripts/build_unsigned_dmg.sh`（已在 main 分支）

```bash
./scripts/build_unsigned_dmg.sh "Talky-2026.03.27-unsigned"
```

| 能力 | 说明 |
|------|------|
| **默认 DMG 路径** | 空白可写卷 → `ditto` 拷贝 stage → `hdiutil convert` → UDZO |
| **SPARSE 默认** | 空白卷优先 `-type SPARSE`，减少 dense UDIF 卡住 |
| **`/tmp` 工作区** | 默认 ditto 到 `/tmp/talky-hdiutil.*`，最终 DMG `mv` 到 `release/` |
| **回退链** | ditto 失败 → `create -srcfolder` UDZO → UDRO + convert |
| **PyInstaller** | 修正 plist；**不要** `--hidden-import pyobjc-framework-AVFoundation`，保留 `AVFoundation` |
| **签名** | ad-hoc `codesign` + 麦克风 entitlement |

---

## 3. 环境变量（调试 / 覆盖）

| 变量 | 作用 |
|------|------|
| `TALKY_DMG_SKIP_TMP_HDIUTIL=1` | 不复制到 /tmp |
| `TALKY_HDIUTIL_VERBOSE=1` | hdiutil 详细日志 |
| `TALKY_DMG_TRY_SRCFOLDER_FIRST=1` | 优先 srcfolder |
| `TALKY_DMG_BLANK_UDIF=1` | 跳过 SPARSE，只用 dense UDIF |
| `TALKY_DMG_FANCY=1` | Finder 布局慢路径 |

---

## 4. 调试信息收集

若出问题，新 session 应收集：

| 文件 | 内容 |
|------|------|
| `~/.talky/logs/debug.log` | `TrayApp.show()` / `_verify_tray_visible()` / `Restart requested` 诊断行 |
| `~/.talky/logs/error-msg.md` | 自动记录的错误（含版本、settings 摘要） |
| `~/.talky/settings.json` | 当前配置 |
| `~/Library/Logs/DiagnosticReports/Talky-*.ips` | macOS crash report |

---

## 5. 近期高频报错与根因（已定位已修复）

1. `module 'mlx.core' has no attribute 'array'`
   - 根因：ABI 不匹配的扩展（如 `core.cpython-39-*.so`，但 app 是 py3.12）
   - 修复：安装器要求主次版本匹配 + 重装前清理残留
2. `Processing failed: [Errno 2] No such file or directory: 'ffmpeg'`
   - 根因：音频路径直接传给 `mlx_whisper`
   - 修复：改为传入内存波形数组

---

## 6. 关键提交历史

```
faab99b fix(tray): use LaunchServices restart to fix tray icon missing after relaunch
d833b66 docs: add FEATURES.md for release/DMG parity (startup gate, Ollama, cloud)
799cc81 style(onboarding): improve model prep page layout and spacing
d6fac61 fix(hotkey): use CoreFoundation imports for CFRunLoop functions
749ed7f feat(onboarding): add "Download in Terminal" button and UI feedback on model prep page
```

UI 大合并（4-tab Dashboard）尚未提交，当前为 working tree 改动。

---

## 7. 新 session 一句话目标

用 UI 合并后的代码**重新打 DMG**，验证 4-tab Dashboard 在打包后正常工作，然后进入 UI 打磨阶段。
