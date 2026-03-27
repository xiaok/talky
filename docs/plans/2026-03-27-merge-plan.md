# Merge Plan — 状态记录（给新 session）

**日期**: 2026-03-27
**分支**: `main`
**上次提交**: `faab99b fix(tray): use LaunchServices restart to fix tray icon missing after relaunch`

---

## 0. 最新进展快照（本次会话收敛）

> 这一节用于"开新 session 快速接手"，优先看这里。

### 已完成的合并工作

原计划文档将 merge plan 分为 6 个文件组。**全部已合并完成**，当前 main 分支已包含所有功能：

| 计划项 | 状态 | 说明 |
|--------|------|------|
| `talky/asr_service.py` | ✅ 已合并 | 懒加载 mlx_whisper、`is_model_available()`、`_resolve_model_reference()`、无 ffmpeg 依赖 |
| `talky/controller.py` | ✅ 已合并 | 懒 ASR、cloud/remote 模式、`__MODEL_NOT_FOUND__` 拦截、`update_dictionary()` 方法 |
| `talky/ui.py` | ✅ 已合并 | **4-tab Dashboard + 所有新功能**（见下方详情） |
| `main.py` | ✅ 已合并 | macOS Foundation、fcntl 锁、AppKit、deferred 检查、cleanup |
| `talky/debug_log.py` | ✅ 已合并 | `append_debug_log` 线程安全写入 |
| DMG 构建脚本 | ✅ 已合并 | SPARSE 空白卷 + ditto + UDZO |

### 本次会话完成的 UI 大合并（核心改动）

**`talky/ui.py`** 从 486 行的单页 SettingsWindow 恢复为 2281 行的 4-tab Dashboard：

| Tab | 类 | 功能 |
|-----|-----|------|
| **Home** | `HomeTab` | Logo、版本号、Fn/快捷键使用提示（Keycap 徽章风格）、GitHub Star 卡片、版本更新横幅（`VersionChecker`） |
| **History** | `HistoryTab` | 左栏日期侧边栏 + 右栏聊天气泡式历史记录展示 |
| **Dictionary** | `DictionaryTab` | 3 列网格 `DictionaryWordCard`、hover 显示 Edit/Delete、`WordEditDialog` 弹窗编辑 |
| **Configs** | `ConfigsTab` | Radio 热键选择组、处理模式（Local/Remote/Cloud）、Cloud URL/Key 动态显隐、模式校验、Save + Reset 按钮 |

**样式**: `NATIVE_STYLESHEET`（macOS 原生风格：分段 tab 栏、Keycap 徽章、SectionFrame、ChatBubble、WordCard 等）。`IOS26_STYLESHEET` 保留为别名，`onboarding.py` 和 `startup_gate.py` 引用不受影响。

**保留的所有新功能**:
- `_restart_current_process()` — LaunchServices 重启（解决 tray icon 消失）
- `_verify_tray_visible()` — 200ms 延迟 tray 诊断
- `ModelSetupDialog` + `_ModelDownloadThread` — Whisper 模型下载
- `ResultPopupWindow` — 浮动结果弹窗（slide+fade 动画）
- 错误报告菜单项、external show signal watcher
- `CustomHotkeyCaptureDialog` — 自定义热键录制

**配套改动**:
- `talky/history_store.py` — 新增 `list_dates()` 和 `read_entries()` 方法
- `talky/controller.py` — 新增 `update_dictionary()` 方法

### 未提交的改动

当前有 19 个文件未提交（`git diff --stat`）。需要用户决定是否提交或先测试。

---

## 1. 新 session 需要做的事

### 优先级 P0 — 验证当前改动

1. **跑一次 `python3 main.py`**，确认 4-tab Dashboard 能正常打开
   - Home tab 显示正常（logo、版本、keycap 提示）
   - History tab 日期列表 + 条目展示
   - Dictionary tab 添加/编辑/删除词条
   - Configs tab 全部表单字段、模式切换、Save/Reset
2. **测试 Reset 流程**: 在 Configs tab 点 Reset → 确认对话框 → 应用重启 → tray icon 出现
3. **测试 Local/Remote/Cloud 模式切换**: 切换模式后 cloud URL/Key 字段正确显隐
4. **打 DMG 并安装测试**: `./scripts/build_unsigned_dmg.sh "test"`

### 优先级 P1 — UI 打磨

1. **Onboarding 样式迁移**: `onboarding.py` 和 `startup_gate.py` 仍用 `IOS26_STYLESHEET` 别名指向 `NATIVE_STYLESHEET`，但部分 objectName 可能未对齐（如按钮 objectName），需逐个确认视觉效果
2. **i18n 完整性**: `_ZH` 字典已有 78 个 key，但 HomeTab 的 GitHub star 描述等仍硬编码英文
3. **ConfigsTab 字段对齐**: 确认 `collect_settings()` 输出的所有字段都能被 `AppSettings` 正确接受

### 优先级 P2 — 质量

1. 提交改动并更新交接文档
2. 跑全部测试 `python3 -m pytest tests/`
3. 更新 `docs/FEATURES.md` 反映 4-tab UI

---

## 2. 文件级改动清单

### 本次会话改动的文件

| 文件 | 行数变化 | 说明 |
|------|----------|------|
| `talky/ui.py` | 486 → 2281 | 4-tab Dashboard + NATIVE_STYLESHEET + 全部新功能 |
| `talky/history_store.py` | 23 → 50 | 新增 `list_dates()`, `read_entries()` |
| `talky/controller.py` | +8 | 新增 `update_dictionary()` |

### 已有但未改动的关键文件

| 文件 | 说明 |
|------|------|
| `talky/onboarding.py` | Ollama 安装向导，引用 `IOS26_STYLESHEET`（现指向 NATIVE） |
| `talky/startup_gate.py` | 启动前 Ollama/Cloud 就绪检查 |
| `talky/models.py` | `AppSettings` 数据模型，含 `mode`, `cloud_api_url`, `cloud_api_key` |
| `talky/version_checker.py` | `VersionChecker` + `CURRENT_VERSION` |
| `talky/dictionary_entries.py` | `DictionaryEntry` 解析 |
| `talky/debug_log.py` | `append_debug_log()` |
| `talky/error_report.py` | `append_error_report()` |
| `main.py` | 入口，导入 `SettingsWindow`, `TrayApp` |

---

## 3. 类结构速查

```
talky/ui.py (2281 lines)
├── _ZH dict (78 keys)
├── _tr(), _asset_path(), _clear_layout(), _entry_to_line(), _load_pixmap(), _make_keycap()
├── _restart_command(), _restart_current_process(), _find_app_bundle_path()
├── NATIVE_STYLESHEET (macOS native)
├── IOS26_STYLESHEET = NATIVE_STYLESHEET (alias)
├── CustomHotkeyCaptureDialog
├── WordEditDialog
├── DictionaryWordCard
├── HomeTab
├── HistoryTab
├── DictionaryTab
├── ConfigsTab (含 _validate_mode_ready, _save_settings, _reset_settings)
├── SettingsWindow (4-tab Dashboard, segmented bar, fade-in, auto-save on close)
├── TrayApp (model setup, restart, tray diagnostics, error report, external signal watcher)
├── ResultPopupWindow (floating, slide+fade animation)
├── _ModelDownloadThread
├── ModelSetupDialog
└── _PollingTqdm
```

---

## 4. 已修复的问题汇总

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | Tray icon 重启后消失 | `os.execv` 同 PID，macOS 不重新注册 NSStatusItem | `open` via LaunchServices 全新 PID |
| 2 | Whisper 依赖 ffmpeg | 音频路径直接传给 mlx_whisper | 改传内存 float32 波形 |
| 3 | `mlx.core` 无 `array` 属性 | ABI 不匹配的扩展 | 安装器要求主次版本匹配 + 清理残留 |
| 4 | remote 模式不持久 | 无 mode 字段 | 新增 `mode=remote` 语义 |
| 5 | 错误无记录 | 无 | 自动写入 `~/.talky/logs/error-msg.md` |

---

## 5. 调试信息收集

若出问题，新 session 应收集：

| 文件 | 内容 |
|------|------|
| `~/.talky/logs/debug.log` | 含 `TrayApp.show()` / `_verify_tray_visible()` / `Restart requested` 诊断行 |
| `~/.talky/logs/error-msg.md` | 自动记录的错误（含版本、settings 摘要） |
| `~/.talky/settings.json` | 当前配置 |
| `~/Library/Logs/DiagnosticReports/Talky-*.ips` | macOS crash report |

---

## 6. DMG 构建参考

脚本: `scripts/build_unsigned_dmg.sh`

```bash
./scripts/build_unsigned_dmg.sh "Talky-2026.03.27-unsigned"
```

| 环境变量 | 作用 |
|----------|------|
| `TALKY_DMG_SKIP_TMP_HDIUTIL=1` | 不复制到 /tmp |
| `TALKY_HDIUTIL_VERBOSE=1` | hdiutil 详细日志 |
| `TALKY_DMG_TRY_SRCFOLDER_FIRST=1` | 优先 srcfolder |
| `TALKY_DMG_BLANK_UDIF=1` | 跳过 SPARSE |
| `TALKY_DMG_FANCY=1` | Finder 布局慢路径 |
