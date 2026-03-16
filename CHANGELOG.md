# 更新日志 / Changelog

## v2.9.0 (2026-03-16)

### ✨ 新功能 / Features

- **离线引擎（Kokoro 本地边车）**：新增 `local_kokoro` Provider，可在设置页一键下载/校验/卸载并切换在线/离线；下载链路强制 SHA256 校验并内置健康检查；安装目录固定到 `%APPDATA%/Anki-TTS-Edge/providers/kokoro/`。
  **Offline engine (Local Kokoro sidecar)**: Added `local_kokoro` provider with one-click download/validate/uninstall and online/offline switch from Settings. Downloads are SHA256-verified with built-in healthcheck, installed under `%APPDATA%/Anki-TTS-Edge/providers/kokoro/`.

- **TTSProvider 抽象层**：统一主生成入口，并在返回结构中预留 `timestamps`（离线 V1 返回空，未来可无痛补齐）。
  **TTSProvider abstraction**: Unified the generation pipeline and reserved `timestamps` in the return structure (offline V1 returns empty; future upgrades won't require main-logic refactors).

### 🔧 修复 / Fixes

- **离线运行时更稳的默认下载项**：默认下载 `*-win-x64-*-MT-Release.tar.bz2` 运行时包（含可用的 `sherpa-onnx-offline-tts.exe`），并通过 manifest `version` 自动升级旧 manifest，避免卡死/缺依赖导致不可用。
  **More reliable offline runtime default**: Default download now uses the `*-win-x64-*-MT-Release.tar.bz2` runtime bundle (includes a working `sherpa-onnx-offline-tts.exe`) and auto-upgrades older manifests by version to avoid hangs/missing-dependency failures.

- **模型文件名兼容**：自动识别 `model*.onnx`（如 `model.int8.onnx`），避免解压成功但校验失败。
  **Model filename compatibility**: Auto-detects `model*.onnx` (e.g. `model.int8.onnx`) to prevent "extracted but not found" validation failures.

## v2.8.2 (2026-03-13)

### 🔧 修复 / Fixes

- **监听语义正式拆分**：设置项现在区分“复制后生成音频”“鼠标划选生成音频”“双语音模式”“划词双语音模式”，首页双生成按钮与划词卫星双点不再共享同一个旧字段。
  **Monitoring semantics split cleanly**: Settings now distinguish between copy-triggered generation, mouse-selection generation, dual voice mode, and selection dual voice mode. The home view A/B buttons and the selection satellite A/B dots no longer depend on the same legacy flag.

- **设置页分组与文案重排**：按“播放 / 声音模式 / 划词模式 / 复制模式 / 窗口 / 存储 / 维护”重排设置页，并将“鼠标划选生成音频”更名为“划词单语音模式”，与“划词双语音模式”并排。
  **Settings page regrouped and renamed**: Reorganized settings into Playback, Voice Mode, Selection Mode, Copy Mode, Window, Storage, and Maintenance, and renamed the selection single-toggle to “Selection Single Voice Mode” so it sits next to the dual-selection toggle.

- **修复 Ctrl+C 复制后只填文本不生成的问题**：剪贴板监听现在会走统一生成入口，自动使用最新声音生成音频，并按自动播放设置决定是否立即朗读。
  **Fix copied text only filling the input without generating audio**: Clipboard monitoring now goes through the unified generation pipeline, uses the latest voice automatically, and respects autoplay for immediate playback.

- **修复生成后 MP3 文件到剪贴板失效**：文件剪贴板写入改为带重试的 `CF_HDROP` 方案，并在写入前抑制内部监听，避免刚生成的 MP3 再反向干扰文本监听。
  **Fix broken “put MP3 on clipboard after generation” flow**: File clipboard writes now use a retrying `CF_HDROP` path and suppress the internal monitor before writing so generated MP3 copies no longer feed back into text monitoring.

- **修复历史页按钮失效**：历史项外层不再吞掉“播放 / 删除”按钮事件，清空全部改回标准 `page.dialog` 链路。
  **Fix inactive history controls**: The outer history item container no longer swallows Play/Delete clicks, and Clear All now uses the standard `page.dialog` flow.

- **降低划词提示与监听延迟**：划词优先尝试直接读取当前控件选区，失败时才退回 `Ctrl+C`，同时降低卫星与监听轮询延迟。
  **Reduce selection prompt latency**: Selection capture now first tries direct control selection access before falling back to `Ctrl+C`, and both satellite and monitor polling have been tightened for faster response.

- **修复划词与复制链路串扰**：划词捕获不再复用剪贴板生成回调，内部选区读取和外部 `Ctrl+C` 生成被彻底拆分，避免未点 `GO` 自动生成以及系统剪贴板被划词流程污染。
  **Fix cross-talk between selection and clipboard flows**: Selection capture no longer reuses the clipboard-generation callback. Internal selection reads and external `Ctrl+C` generation are now split cleanly, preventing auto-generation without `GO` and avoiding clipboard pollution from the selection flow.

- **修复 A / B 与声音列表 1 / 2 的语义错位**：双语音状态从“latest / previous”迁移为稳定的 `left / right` 槽位，首页和划词卫星统一固定为 `A -> 声音列表 1`、`B -> 声音列表 2`。
  **Fix A/B mapping drift against Voice List 1 / 2**: Dual-voice state now uses stable `left / right` slots instead of the rotating `latest / previous` model, so both the home screen and the selection satellite now consistently map `A -> Voice List 1` and `B -> Voice List 2`.

- **新增运行时自检脚本**：添加 `tools/flet_runtime_selfcheck.py`，在打包前验证视图构造、设置联动、历史页回调和当前 Flet 运行时签名，减少“进程活着但界面已经报错”的漏检。
  **Add runtime self-check script**: Added `tools/flet_runtime_selfcheck.py` to validate view construction, settings coupling, history callbacks, and the active Flet runtime signature before packaging, reducing false positives where the process stays alive but the UI is already broken.

- **修复划词模式仍会扰乱系统剪贴板**：内部划词回退复制不再回放整份原始剪贴板句柄，而是只恢复用户真正可见的安全格式，降低文本复制/粘贴被污染的概率。
  **Fix selection mode still disturbing the system clipboard**: Internal selection fallback no longer replays the entire raw clipboard payload and instead restores only safe user-visible formats, reducing the chance of corrupting normal copy/paste behavior.

- **修复 MP3 文件到剪贴板“能写不能粘”**：文件剪贴板改为标准 `CF_HDROP + Preferred DropEffect` 结构，并在本地验证可读回。
  **Fix MP3 clipboard writes that could not actually paste**: File clipboard writes now use the standard `CF_HDROP + Preferred DropEffect` structure and were locally validated by round-trip reads.

- **优化重复生成耗时**：相同文本/声音/参数的请求现在直接命中本地音频缓存，避免重复走 `edge-tts` 生成。
  **Improve repeated generation latency**: Identical text/voice/parameter requests now hit a local audio cache instead of regenerating through `edge-tts`.

- **修复非“声音”页时后台功能像失效**：复制后生成、划词生成、历史页播放/删除不再依赖当前 `HomeView` 已挂载，隐藏页状态更新统一走安全刷新链路。
  **Fix background features appearing broken outside the Voices tab**: Clipboard generation, selection generation, and history play/delete no longer assume the Home view is currently mounted; hidden view updates now go through a safe refresh path.

- **修复反复划词导致卡死和高占用**：划词流程新增忙时断路器，在卫星窗等待点击或划词生成进行中时直接忽略新的划词触发，避免后台捕获与生成堆积。
  **Fix repeated selection causing freezes and high CPU/memory use**: The selection flow now has a busy-state circuit breaker that ignores new selection triggers while the satellite is awaiting input or generation is already running.

- **修复历史页右上角“清空全部”无响应**：历史清空确认框切换到当前 Flet 运行时兼容的 `page.open(dialog) / page.close(dialog)` 链路，避免旧式 `page.dialog` 打开方式在打包版中看起来无反应。
  **Fix the unresponsive “Clear All” action in the history header**: The history confirmation dialog now uses the runtime-compatible `page.open(dialog) / page.close(dialog)` flow instead of the legacy `page.dialog` pattern that appeared inert in packaged builds.

## v2.8.1 (2026-03-13)

### 🔧 修复 / Fixes

- **修复打包版启动时缺失 `flet_desktop` 运行时**：将 `flet` 与 `flet-desktop` 固定到同一版本，并在 PyInstaller 构建中显式收集 `flet_desktop` 模块与资源，解决 EXE 启动后立即报 `ModuleNotFoundError: No module named 'flet_desktop'` 的问题。
  **Fix missing `flet_desktop` runtime in packaged builds**: Pinned `flet` and `flet-desktop` to the same version and explicitly collected `flet_desktop` in PyInstaller so the EXE no longer fails on startup with `ModuleNotFoundError: No module named 'flet_desktop'`.

- **修复主题配色与当前 Flet 运行时不兼容导致的启动异常**：主题构造改为兼容模式，遇到旧版 `ColorScheme` 不支持的字段时自动降级，解决 `surface_variant` 触发的启动错误。
  **Fix startup error caused by ColorScheme incompatibility**: Theme creation now falls back gracefully when older Flet runtimes do not accept newer `ColorScheme` fields, fixing the startup failure triggered by `surface_variant`.

- **修复视图类写入只读 `page` 属性导致的启动异常**：`HomeView`、`HistoryView`、`SettingsView` 改用私有页面引用，兼容当前 Flet 控件基类的只读属性约束。
  **Fix startup error caused by writing to the read-only `page` property**: `HomeView`, `HistoryView`, and `SettingsView` now store the host page in a private reference instead of assigning to Flet's read-only `page` property.

- **修复首屏和页面交互的强延迟**：语音列表改为“优先本地缓存、命中缓存时再后台刷新”，顶部三页切换改为单宿主视图切换，托盘与卫星轮询改为惰性/降频启动，长文本播放不再无上限构建逐词高亮控件。
  **Fix severe UI latency on startup and page interactions**: Voice loading now prefers local cache and only refreshes in the background when cache exists, the top navigation uses a single hosted view instead of a three-page stack, tray/satellite work is lazily initialized or throttled, and long playback sessions no longer build unbounded per-word highlight controls.

---

## v2.8 (2026-03-13)

### 🔧 修复 / Fixes

- **修复安装后缺依赖直接崩溃**：补齐 `pynput` 与 `pywin32` 依赖，并同步更新打包入口，避免按 README 安装后因监听或文件剪贴板模块缺失而无法启动。
  **Fix startup crashes caused by missing dependencies**: Added `pynput` and `pywin32` to the runtime requirements and updated the packaging entry so fresh installs no longer fail before launch.

- **修复托盘/卫星恢复主窗口失效**：移除残留旧版 Flet 窗口 API，统一切换到 `page.window.*` 新接口，恢复托盘显示/隐藏与卫星双击唤醒链路。
  **Fix tray/satellite window restore flow**: Removed legacy Flet window calls and standardized on the current `page.window.*` API so tray restore and satellite double-click bring the main window back reliably.

- **修复历史回放状态串音**：播放历史记录时现在会同步刷新文本与时间戳，避免沿用上一条音频的高亮、句导航与播放状态。
  **Fix state leakage when replaying history**: History playback now refreshes the active text and timestamps so highlighting, sentence navigation, and playback state always match the selected record.

- **修复历史缓存只删记录不删文件**：达到历史上限时会同步删除被淘汰记录对应的音频和 `.timestamps.json`，磁盘占用不再无限增长。
  **Fix cache trimming leaving orphaned files**: When history exceeds the configured limit, the app now deletes the evicted audio file and matching `.timestamps.json` instead of only trimming the JSON list.

- **修复音频文件秒级重名覆盖**：输出文件名改为“微秒时间戳 + 短 UUID”，高频连续生成不会再静默覆盖前一个文件。
  **Fix silent audio overwrite on rapid generation**: Output filenames now use a microsecond timestamp plus a short UUID, preventing collisions during back-to-back generations.

- **修复主题与设置持久化不一致**：统一使用 `appearance_mode` 存储主题，并兼容旧版 `theme_dark` 设置迁移；同时解除剪贴板监听与划词监听的错误绑定。
  **Fix inconsistent settings persistence**: Theme storage now uses a single `appearance_mode` key with compatibility migration from `theme_dark`, and clipboard monitoring is no longer incorrectly coupled to selection monitoring.

- **修复播放监控并发竞态**：播放、高亮与暂停恢复监控改为单实例运行，避免多个后台协程同时修改 UI 和播放状态。
  **Fix playback monitor race conditions**: Playback/highlight monitoring is now single-instance, preventing multiple background tasks from mutating the UI and playback state at the same time.

### 📚 文档 / Docs

- **新增架构文档**：补充 `ARCHITECTURE.md`，固化主流程、状态边界、持久化规则与本轮修复决策，降低后续维护成本。
  **New architecture document**: Added `ARCHITECTURE.md` to document the runtime flow, state boundaries, persistence rules, and the decisions behind this stabilization pass.

---

## v2.7 (2026-03-01)

### ✨ 新功能 / Features

- **快捷打开数据目录**：在设置界面新增“打开数据目录”按钮（存储了音频、历史记录、配置文件等），方便高级管理。
  **Quick access to data directory**: Added a new "Open Data Directory" button in Settings to easily access audio files, history, and config files.

---

## v2.6 (2026-03-01)

### ✨ 改进 / Improvements

- **中性配色主题**：浅色/深色模式均改为 Slate 蓝灰色系，无强烈色彩倾向，视觉中性专业，适合所有用户。
  **Neutral color theme**: Both light/dark modes now use a Slate blue-grey palette with no strong color bias — clean, professional, and universally comfortable.

- **设置即改即存**：移除"保存设置"按钮，所有设置项修改后立即生效并自动保存，减少不必要的点击。
  **Instant settings save**: Removed the "Save Settings" button. All setting changes now take effect and are saved immediately, eliminating unnecessary clicks.

- **README 核心特性精简**：核心特性小节不再堆积更新日志条目，仅保留软件功能的简洁描述。
  **README features cleanup**: The Core Features section now contains only clean feature descriptions, not changelog entries.

---

## v2.5 (2026-03-01)

### ✨ 新功能 / Features

- **用户数据统一管理**：所有用户生成的文件（设置、历史、音频、日志、语音缓存）迁移至 `%APPDATA%/Anki-TTS-Edge/`，目录使用英文命名（`audio/`、`logs/`），全球通用。首次启动自动迁移旧数据。
  **Centralized user data**: All user-generated files (settings, history, audio, logs, voice cache) moved to `%APPDATA%/Anki-TTS-Edge/` with English-named directories (`audio/`, `logs/`). Automatic one-time migration from old paths on first launch.

- **深色/浅色主题重新设计**：浅色模式采用暖色调 Teal 主色 + Stone 中性色，深色模式采用高对比 Teal-400 + Stone-900 背景，视觉更舒适自然。UI 控件全面使用语义化颜色 token（`primary`、`surface`、`primaryContainer`），主题切换无色彩断裂。
  **Theme redesign**: Light mode uses warm Teal-600 primary + Stone neutral surfaces; dark mode uses vibrant Teal-400 + Stone-900 backgrounds. All UI components now use semantic color tokens for seamless theme switching.

---

## v2.4 (2026-03-01)

### ✨ 新功能 / Features

- **即点即读精确定位**：点击文段中任意单词/字符时，直接从该位置开始播放，不再跳转到句首，定位更精确。
  **Precise click-to-play**: Clicking any word/character in the text now starts playback from that exact position instead of jumping to the sentence start, providing more precise control.

### 📦 构建 / Build

- **构建方式切换为 onedir 模式**：从 PyInstaller 单文件 (onefile) 切换为文件夹 (onedir) 模式，大幅提升 Windows 下的启动速度（消除杀毒软件扫描导致的延迟）。
  **Switch to onedir build**: Changed from PyInstaller single-file (onefile) to folder (onedir) mode, significantly improving Windows startup speed by eliminating antivirus scan delays.

---

## v2.3 (2026-03-01)

### 🔧 修复 / Fixes

- **修复 TTS 生成失败**：升级 `edge-tts` 至 7.2.7，修复微软 API 认证令牌过期导致的 403 错误，恢复所有语音的正常生成能力。
  **Fix TTS generation failure**: Upgraded `edge-tts` to 7.2.7, resolving 403 errors caused by expired Microsoft API authentication tokens. All voices are now functional again.

- **修复单词高亮跟随失效**：适配 `edge-tts` 7.x API 变更（`boundary` 参数默认值从 `WordBoundary` 改为 `SentenceBoundary`），显式传入 `boundary='WordBoundary'` 以恢复单词级时间戳和实时高亮。
  **Fix word-level highlight sync broken**: Adapted to `edge-tts` 7.x API change where the `boundary` parameter default changed from `WordBoundary` to `SentenceBoundary`. Now explicitly passes `boundary='WordBoundary'` to restore word-level timestamps and real-time highlighting.

- **修复重复函数定义** (`handle_generate_a`)：删除 `main.py` 中残留的重复函数定义。
  **Fix duplicate function definition** (`handle_generate_a`): Removed leftover duplicate definition in `main.py`.

- **修复窗口事件双重绑定**：移除旧 API 的事件绑定 (`page.on_window_event`)，仅保留新 API (`page.window.on_event`)，避免窗口关闭/最小化事件被触发两次。
  **Fix double window event binding**: Removed legacy API binding (`page.on_window_event`), keeping only the new API (`page.window.on_event`) to prevent duplicate event triggers on close/minimize.

- **修复 `MonitorManager.stop()` 缺失**：添加 `stop()` 方法作为 `stop_monitors()` 的别名，修复应用重启时的 `AttributeError`。
  **Fix missing `MonitorManager.stop()`**: Added `stop()` as an alias for `stop_monitors()`, fixing `AttributeError` on app restart.

- **修复卫星轮询中无效的 `locals()` 检查**：`satellite_loop` 中的 `monitor_manager` 是闭包变量，`locals()` 永远无法检测到它，已改用 `hasattr()` 检查。
  **Fix invalid `locals()` check in satellite loop**: `monitor_manager` is a closure variable, so `locals()` could never detect it. Replaced with `hasattr()`.

### ⚡ 优化 / Improvements

- **窗口缩放防抖**：拖拽调整窗口大小时，设置文件不再每帧写入磁盘，改为 300ms 防抖延迟写入，大幅降低 I/O 压力。
  **Window resize debounce**: Settings are no longer written to disk on every resize frame. Added 300ms debounce to significantly reduce I/O during window dragging.

- **日志改为追加模式**：剪贴板监控日志从覆盖模式 (`filemode='w'`) 改为 `RotatingFileHandler` 追加模式，保留历史诊断信息，文件上限 1MB 自动轮转。
  **Log rotation**: Clipboard monitor logging changed from overwrite mode (`filemode='w'`) to `RotatingFileHandler` with 1MB cap, preserving diagnostic history.

- **消除裸异常捕获**：全项目 14 处 `except: pass` 替换为 `except Exception`，避免吞掉关键错误信息。
  **Eliminate bare excepts**: All 14 instances of `except: pass` replaced with `except Exception` across the project to prevent silently swallowing critical errors.

- **删除死代码**：移除 `audio_gen.py` 中不再被调用的 `generate_audio` 和 `generate_audio_edge_tts_async` 函数及未使用的 `threading` 导入，代码行数减少 40%。
  **Remove dead code**: Removed unused `generate_audio` and `generate_audio_edge_tts_async` functions along with the unused `threading` import from `audio_gen.py`, reducing file size by 40%.

---

## v2.2 (2026-02-26)

- 历史记录深度清理：自动扫描音频目录，清除孤立的音频文件和配套数据文件。
  Deep history cleanup: Automatically scans audio directory and removes orphaned audio and metadata files.

## v2.1

- 高亮跟随朗读，即点即读，智能导航。
  Real-time word highlighting, click-to-play, smart sentence navigation.

## v2.0

- 全新 Flet (Flutter) 重构，现代化 UI。
  Full Flet (Flutter) rewrite with modern UI.
