# Anki-TTS-Edge Architecture

## 1. 核心运行链路

- `Anki-TTS-Flet/main.py`
  - Flet 主窗口入口。
  - 负责页面初始化、托盘/卫星窗/监听器接线、播放状态机与视图联动。
- `Anki-TTS-Flet/core/audio_gen.py`
  - 使用 `edge-tts` 生成音频与词级时间戳。
  - 生成文件统一落到 `%APPDATA%/Anki-TTS-Edge/audio/`。
- `Anki-TTS-Flet/core/tts_provider.py` / `Anki-TTS-Flet/core/tts_manager.py`
  - TTS 抽象层与引擎选择器（`edge_online` / `local_kokoro`）。
  - 对主链路只暴露统一的 `SynthesisRequest -> SynthesisResult`，并预留 `timestamps` 字段。
- `Anki-TTS-Flet/core/local_engine_manager.py`
  - 管理离线引擎（Kokoro via sherpa-onnx）的下载、SHA256 校验、安装、卸载与健康检查。
  - 所有离线运行时与模型文件固定落到 `%APPDATA%/Anki-TTS-Edge/providers/kokoro/`（主程序 EXE 保持干净）。
- `Anki-TTS-Flet/core/history.py`
  - 维护历史记录 JSON。
  - 历史上限不仅裁剪记录，还必须同步删除被挤出的音频与时间戳文件。
- `Anki-TTS-Flet/core/clipboard.py`
  - 负责剪贴板监听、划词复制注入、卫星窗进程通信。
- `Anki-TTS-Flet/core/satellite.py`
  - 独立 `tkinter` 进程，显示单点/双点悬浮操作入口。
- `Anki-TTS-Flet/ui/*.py`
  - `home_view.py` 负责输入、声音列表、播放控件与高亮文本覆盖层。
  - `history_view.py` 负责历史展示与删除/清空操作。
  - `settings_view.py` 负责主题、监听、托盘、窗口尺寸、数据目录等设置项。

## 2. 关键状态边界

- 播放状态只以 `main.py` 内的 `current_audio_state` 为唯一真源。
- 切换音频文件时，必须同步重置：
  - `path`
  - `timestamps`
  - `text`
  - `current_sentence_index`
  - `current_playback_start_ms`
  - `stop_playback_at_ms`
- 播放监控协程必须保持单实例。
  - 新播放开始时提升 `run_id`，旧监控循环自动失效退出。
  - 暂停/恢复不能重复启动监控循环。

## 3. 持久化规则

- 用户数据统一存储到 `%APPDATA%/Anki-TTS-Edge/`。
- 只允许以下长期文件存在：
  - `voice_settings.json`
  - `history.json`
  - `voices_cache.json`
  - `logs/monitor_debug.log`
  - `audio/*.mp3`
  - `audio/*.timestamps.json`
  - `providers/kokoro/manifest.json`（离线引擎清单，可升级）
  - `providers/kokoro/install_state.json`（离线引擎安装状态）
  - `providers/kokoro/runtime/**`（离线运行时解压内容）
  - `providers/kokoro/model/**`（离线模型解压内容）
  - `providers/kokoro/downloads/**`（离线引擎下载缓存）
  - `providers/kokoro/cache/**`（健康检查/临时输出）
- 音频文件名必须全局唯一。
  - 不能只用秒级时间戳，否则高频连续生成会发生覆盖。
  - 当前实现对相同 `文本 + 声音 + 速率 + 音量 + 音高` 使用稳定缓存键。
  - 相同请求直接命中已生成音频，避免重复走 `edge-tts` 网络生成。

## 4. UI / 设置约束

- `appearance_mode` 是主题持久化唯一字段。
  - 旧版 `theme_dark` 仅做兼容迁移，不再继续写入。
- 剪贴板监听与划词监听是两个独立能力：
  - `monitor_clipboard_enabled`
  - `monitor_selection_enabled`
- 双语相关状态拆分为两个字段：
  - `dual_voice_mode_enabled`
  - `selection_dual_mode_enabled`
- 声音选择状态使用稳定槽位：
  - `selected_voice_left`
  - `selected_voice_right`
- 离线 Kokoro 音色选择使用独立槽位（与微软 voice 解耦）：
  - `local_kokoro_sid_left`
  - `local_kokoro_sid_right`
  - 音色目录由 `Anki-TTS-Flet/core/kokoro_voice_catalog.py` 固化（按官方 sid->name 映射，避免“顺推生成”导致错配）。
- 兼容迁移：
  - 旧版 `selected_voice_previous -> selected_voice_left`
  - 旧版 `selected_voice_latest -> selected_voice_right`
- 划词单语音模式对应：
  - `monitor_selection_enabled`
- 约束：
  - `selection_dual_mode_enabled = true` 时，`dual_voice_mode_enabled` 必须同步为 `true`
  - `selection_dual_mode_enabled = true` 时，`monitor_selection_enabled` 也必须同步为 `true`
  - 首页 `A/B` 双生成按钮只由 `dual_voice_mode_enabled` 控制
  - 划词卫星 `A/B` 双点只由 `selection_dual_mode_enabled` 控制
  - 剪贴板监听不依赖划词监听，也不应被“双语模式”绑死

## 5. 监听 / 生成联动规则

- 剪贴板回调必须带来源语义：
  - `clipboard`
- `clipboard` 来源：
  - 更新输入框文本
  - 自动按 `selected_voice_right` 生成音频
  - 是否立即朗读由 `autoplay_enabled` 决定
- 划词捕获回调是独立通道，不再复用剪贴板生成回调：
  - 更新输入框文本
  - 不直接自动生成
  - 由卫星 `Go` / `A` / `B` 按钮决定是否生成及使用哪个声音
- 首页 / 划词双语音映射固定为：
  - `A -> selected_voice_left`
  - `B -> selected_voice_right`
- 引擎切换必须清空播放状态：
  - 停止并卸载当前音频，清空 `current_audio_state.path/timestamps`，避免“切到在线但仍播放离线旧音频”造成误判。
- 点读/跳句依赖时间戳：
  - 在线（Edge）生成 `words/sentences` 时间戳后才启用。
  - 离线（Kokoro v1）当前不产出时间戳，相关操作应明确提示“不支持”（而不是静默无响应）。
- 监听线程不能直接操作 Flet UI。
  - 必须通过 `page.run_task(...)` 回到主页面事件循环后再更新控件。
- 后台链路不能假定 `HomeView` 当前已挂载。
  - 顶部导航使用单宿主切页时，隐藏页控件虽然仍持有状态，但不能直接 `.update()`。
  - 控制器层统一通过 `home_view._safe_update(...)` 刷新，避免“非声音页时监听 / 历史按钮看起来失效”。
- 设置页分组规则：
  - `播放`
  - `声音模式`
  - `划词模式`
  - `复制模式`
  - `窗口`
  - `存储`
  - `维护`
  - 不再把“复制后生成音频”和“划词单/双语音模式”混排在同一组里
- 划词获取文本的优先级：
  1. 直接读取当前聚焦 `Edit/RichEdit` 的选区，避免污染系统剪贴板
  2. 仅在直读失败时才退回模拟 `Ctrl+C`
  3. 退回复制后只恢复安全格式快照：
     - `CF_UNICODETEXT`
     - `CF_TEXT`
     - `CF_HDROP`
     - `HTML Format`
  4. 禁止再回放整份原始剪贴板句柄数据，否则会污染系统剪贴板
- 生成完成后如果启用了“生成音频后得到 MP3 文件到剪贴板”，必须先抑制监听器，再写入标准 `CF_HDROP + Preferred DropEffect` 文件剪贴板。
- 划词链路必须有忙时断路器：
  - 卫星窗已显示但用户尚未点击时，忽略新的划词触发。
  - 划词生成进行中时，忽略新的划词触发。
  - 卫星窗自动隐藏或关闭时，必须显式清除忙状态。
- 自检脚本：
  - `tools/flet_runtime_selfcheck.py`
  - 用于在打包前快速验证视图构造、设置联动、历史页按钮回调与当前 Flet 运行时签名。

## 6. 已修复的高风险问题

- 修复安装依赖缺失导致的启动即崩：
  - 新增 `pynput`
  - 新增 `pywin32`
- 修复旧版 Flet 窗口 API 残留：
  - 统一为 `page.window.visible`
  - 统一为 `page.window.minimized`
  - 统一为 `page.window.to_front()`
- 修复历史回放复用上一条音频的高亮/时间轴污染。
- 修复历史缓存上限只删 JSON 不删磁盘文件。
- 修复主题设置无法跨重启稳定恢复。
- 修复设置页把剪贴板监听错误绑死到划词监听。
- 修复播放监控协程可重复并发启动导致的状态竞态。
- 修复历史记录展示读取错误字段导致的空信息。
- 修复主逻辑仍读取旧版 `dual_blue_dot_enabled` 导致设置页新旧语义失配。
- 修复历史页外层可点击容器吞掉“播放 / 删除”按钮事件。
- 修复历史页“清空全部”仍走旧 overlay 模式，改为标准 `page.dialog`。
- 修复历史页“清空全部”在当前 Flet 运行时无响应，统一改为 `page.open(dialog) / page.close(dialog)`。
- 修复监听回调在后台线程直接触摸 Flet 控件带来的延迟与不稳定。
- 修复非 `声音` 页时，复制生成 / 划词生成 / 历史播放删除会被隐藏页 `.update()` 打断的问题。
- 修复划词在卫星窗等待点击或生成期间仍继续排队，导致高 CPU / 高内存 / 卡死的问题。

## 7. 当前工程注意事项

- `requirements.txt` 与 README 安装说明必须保持同步，否则用户会按文档装出一个不可运行环境。
- Flet 桌面版打包必须显式带上 `flet_desktop`：
  - 运行时会动态检查该包。
  - PyInstaller 不能只打 `flet_desktop`，还要收集 `flet` 与 `flet_desktop` 的 datas / binaries / hiddenimports。
  - 否则 EXE 启动时会先报 `ModuleNotFoundError: flet_desktop`，随后落入 Flet 内部安装分支并二次崩溃。
  - 即使 `flet_desktop` 已收集，如果漏掉 `flet` 自身数据文件，也会在运行时缺少 `controls/material/icons.json` 这类资源。
- 自定义 `ColorScheme` 必须做版本兼容：
  - 不同 Flet 版本对主题字段支持不完全一致。
  - 启动阶段创建主题时一旦传入不支持的字段，整个应用会在首屏前直接失败。
  - 当前实现会自动剔除旧版本不支持的关键字参数，保证主题降级但程序可启动。
- Flet 控件子类不能覆写 `page`：
  - `Container` / `Control` 基类会提供只读 `page` 属性。
  - 业务代码如果需要持有宿主页引用，统一使用私有字段，例如 `self._host_page`。
- 涉及窗口前置、显示、销毁的 Flet `Window` 方法优先按官方异步接口使用。
- Flet 页面性能约束：
  - 顶部导航必须做单宿主切换，不要再把三页同时挂在一个 `Stack` 里仅靠 `visible` 控制。
  - 托盘与卫星能力默认惰性启动；对应设置关闭时，不要在空闲态保留无意义轮询或系统集成初始化。
  - 语音列表应优先展示本地缓存，只有缓存命中时才做后台刷新；首启无缓存时不要再额外发起第二次刷新。
  - 长文本播放不能无上限构建逐词高亮控件；当前策略是超过阈值后退化为只读文本模式，以换取按钮响应与切页速度。
- 如果未来增加“清理数据目录”能力，必须按类别清理：
  - 音频
  - 历史
  - 日志
  - 语音缓存
  - 设置
  - 离线引擎（providers/kokoro）

## 8. 离线引擎踩坑记录

- Kokoro 模型包内 ONNX 文件名可能是 `model.int8.onnx`（不保证叫 `model.onnx`），安装与校验必须做自动识别。
- Windows 离线运行时优先下载 `*-MT-Release.tar.bz2` 这类打包（静态链接 MSVC runtime，且带齐依赖 DLL）。
  - 单文件 `sherpa-onnx-*-tts-*.exe` 在部分环境下会卡死/不可用（疑似缺 DLL/运行库对话框阻塞），必须避免作为默认项。
