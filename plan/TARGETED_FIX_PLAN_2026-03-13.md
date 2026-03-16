# 定向修复计划

更新时间：2026-03-13 21:05

## 0. 当前执行进度

截至本次修复，以下内容已经落地到代码并完成构建验证：

- `selected_voice_latest / selected_voice_previous` 已迁移为稳定的 `selected_voice_left / selected_voice_right`
- 首页与划词卫星已统一固定为：
  - `A -> 声音列表 1`
  - `B -> 声音列表 2`
- 划词捕获与外部复制生成已拆成两条回调，不再复用同一个“复制后生成”入口
- 划词模式不再因为自身内部复制去触发自动生成
- 历史页播放 / 删除按钮已改为显式关键字参数绑定，减少 Flet 运行时兼容歧义
- MP3 文件剪贴板写入已增加写后校验与重试
- 新增运行时自检脚本：
  - [flet_runtime_selfcheck.py](/D:/软件编写/Anki-TTS-Edge/tools/flet_runtime_selfcheck.py)

本计划中的工程侧任务现在已经全部完成：

- `Python 3.10 compileall` 已通过
- 运行时自检脚本 `tools/flet_runtime_selfcheck.py` 已通过
- 唯一正式输出目录 `dist/` 已重建
- 新 EXE 已完成受控冒烟启动验证

当前只剩最终人工验收：

- 用最新 `dist/Anki-TTS-Edge/Anki-TTS-Edge.exe` 做一次真实操作确认
- 重点验证划词、`Ctrl+C`、历史页和 MP3 文件剪贴板这四条用户链路

补充说明：

- 2026-03-13 晚间第二轮修复又收口了 4 个复测遗留点：
  - 划词回退复制改为“安全格式快照恢复”，重点修复系统剪贴板被扰乱
  - 历史页操作按钮改为更明确的文本按钮，并给记录删除补按路径兜底
  - MP3 文件剪贴板改为标准 `CF_HDROP + Preferred DropEffect`
  - 相同生成请求增加本地缓存命中，降低重复生成等待时间
- 2026-03-13 晚间第三轮修复继续收口了 3 个复测遗留点：
  - 控制器层不再对未挂载的 `HomeView` 强行 `.update()`，解决“非声音页时监听 / 历史操作像失效”
  - 划词流程新增“卫星窗已显示 / 正在生成”忙时断路器，阻止重复划词堆积导致卡死
  - 卫星窗关闭与自动隐藏现在会向主进程回传 `DISMISSED`，用于及时清除划词忙状态

## 1. 文档目的

本文件专门对应当前仍未解决的 6 个问题：

1. 划词单语音 / 划词双语音模式下，用户有时不点 `GO` 也会自动生成音频。
2. 划词双语音模式下，`A / B` 与“声音列表 1 / 声音列表 2”的对应关系混乱。
3. 划词模式会干扰系统剪贴板，导致复制粘贴异常。
4. “复制后生成音频”在 `Ctrl+C` 场景下仍有失效，且该 UI 文案有异常显示。
5. “生成历史”页的播放 / 删除 / 清空全部仍被用户报告失效。
6. “生成音频后得到 MP3 文件到剪贴板”仍未达到可粘贴使用状态。

本计划文件用于：

- 固化当前真实问题，而不是重复靠用户截图转报错。
- 记录已经确认的代码证据。
- 给出后续修复顺序、修改范围和验证矩阵。
- 在聊天窗口失效后，作为下一窗口继续执行的直接入口。

## 2. 当前状态

当前程序已经满足这些前提：

- 主界面可正常启动。
- `dist/` 已恢复为唯一正式构建目录。
- 设置页分组与基础文案已经重排。
- `compileall` 与现有 `flet_selfcheck.py` 均可通过。

因此当前阶段不再是“启动级故障”，而是 **监听 / 生成 / 状态模型 / 历史交互** 四条业务链的定向修复。

## 3. 已确认的代码证据

### 3.1 划词未点 `GO` 却自动生成

现有实现中：

- 划词流程入口在 [clipboard.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/clipboard.py)
  - `simulate_copy()` 会在划词后尝试：
    - 直读选区
    - 失败时退回模拟 `Ctrl+C`
- 统一回调入口在 [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
  - `handle_monitored_text(text, source="clipboard")`
  - 只要来源被识别成 `clipboard`，就会直接调用 `generate_audio_for_voice(...)`

问题点：

- 划词退回 `Ctrl+C` 时，内部复制内容会短暂进入系统剪贴板。
- 剪贴板轮询线程在恢复原剪贴板前，仍可能把这次内部复制识别成真正的外部复制。
- 一旦被识别成 `source="clipboard"`，就会绕过 `GO / A / B` 直接生成。

结论：

- “划词未点 `GO` 就生成”不是随机现象，而是 **内部划词复制与外部剪贴板复制没有被彻底隔离**。

### 3.2 `A / B` 语音映射混乱

当前首页和划词双语音模式用的是“最新 / 上一个”状态模型，而不是“列表 1 / 列表 2”稳定槽位：

- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
  - `selected_voice_latest`
  - `selected_voice_previous`
  - `handle_voice_selected()` 每次点击声音时会做旋转：
    - 当前 `latest -> previous`
    - 新点击声音 -> `latest`
- [home_view.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/ui/home_view.py)
  - `set_selections(latest, previous)`
  - `A` 用 `selected_voice_previous`
  - `B` 用 `selected_voice_latest`
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
  - `handle_satellite_action()` 也是按：
    - `A -> selected_voice_previous`
    - `B -> selected_voice_latest`

问题点：

- 用户的真实心智模型是：
  - `A` 对应声音列表 1
  - `B` 对应声音列表 2
- 当前代码的真实模型却是：
  - `A` 对应上一次选中的声音
  - `B` 对应最近一次选中的声音

结论：

- 这不是单个事件处理 bug，而是 **状态模型本身与产品语义不一致**。
- 后续必须把“latest / previous”迁移为稳定的“left / right”或“voice_1 / voice_2”槽位。

### 3.3 划词模式干扰系统剪贴板

当前干扰来源至少有 3 处：

- [clipboard.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/clipboard.py)
  - `simulate_copy()` 在直读失败后会真实发送 `Ctrl+C`
  - 然后再读剪贴板，再恢复剪贴板快照
- [files.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/files.py)
  - `capture_clipboard_snapshot()` / `restore_clipboard_snapshot()` 会对当前所有剪贴板格式做枚举和回写
- [clipboard.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/clipboard.py)
  - 同时还有一个轮询线程持续 `pyperclip.paste()`

问题点：

- 内部划词复制、剪贴板轮询、原剪贴板恢复三者共享同一个系统剪贴板。
- 这会造成：
  - 用户原本复制的内容被短暂覆盖
  - 某些格式恢复不完整
  - 外部程序刚复制的内容被内部恢复动作打断

结论：

- 当前实现仍然属于“借用系统剪贴板完成划词”，不是真正的无干扰方案。
- 必须把“划词读取”与“外部复制监听”彻底隔离。

### 3.4 “复制后生成音频”仍会失效

静态代码显示：

- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
  - `handle_monitored_text()` 只有 `source == "clipboard"` 才触发生成

结合问题 3 可推断：

- 当划词模式开启时，内部复制和外部 `Ctrl+C` 之间仍有相互覆盖。
- 用户真实执行的 `Ctrl+C` 可能被内部恢复逻辑覆盖，导致监听线程看不到稳定的新文本。

另外，UI 文案里的“复”字异常，更像是：

- 字体渲染问题
- 或文案宽度 / 布局压缩问题

这部分不应混入核心业务修复，需单独做一次 UI 文案显示验证。

### 3.5 “生成历史”页按钮仍被用户报告失效

当前代码表面上已经具备这些绑定：

- [history_view.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/ui/history_view.py)
  - 每条记录内有：
    - `IconButton(PLAY_ARROW, on_click=...)`
    - `IconButton(DELETE, on_click=...)`
  - 清空按钮会打开 `page.dialog`
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
  - `history_view.on_play_audio = handle_history_play`
  - `history_view.on_delete_item = handle_history_delete`
  - `history_view.on_clear_all = handle_history_clear`

但用户仍然在实际 EXE 中报告失效，说明不能仅凭静态代码认定“已经修好”。

当前判断：

- 需要增加真实的点击链路诊断：
  - 按钮点击是否进入 `HistoryView`
  - 回调是否进入 `main.py`
  - 对应记录的 `path` 是否存在
  - 删除时是否遇到文件锁

结论：

- 这是一个 **运行期交互问题**，需要补日志和最小交互冒烟，而不是继续靠静态阅读自信宣布已修复。

### 3.6 MP3 文件剪贴板仍不可用

当前实现：

- [files.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/files.py)
  - `copy_file_to_clipboard(file_path)` 使用 `CF_HDROP`
  - 仅通过 `win32clipboard.SetClipboardData(win32con.CF_HDROP, (abs_path,))`

问题点：

- 这种简化写法在部分目标程序中可能不可粘贴或不可识别。
- 即使写入成功，也可能被后续内部剪贴板恢复逻辑覆盖。

结论：

- 需要把“MP3 文件到剪贴板”单独做成可验证链路，不应再复用当前“乐观写入后假设成功”的逻辑。

## 4. 核心技术决策

### 决策 1：停止使用“latest / previous”作为双语音主状态模型

后续迁移方向：

- 新增稳定槽位：
  - `selected_voice_left`
  - `selected_voice_right`
- 首页：
  - 列表 1 只绑定 `left`
  - 列表 2 只绑定 `right`
- 划词双语音：
  - `A -> left`
  - `B -> right`

兼容策略：

- 启动时把旧的 `selected_voice_latest / selected_voice_previous` 迁移到新字段。
- 迁移完成后，主逻辑不再依赖旧字段。

### 决策 2：把“划词内部复制”与“外部复制监听”彻底隔离

后续方向：

- 划词模式优先只走“非剪贴板读取”。
- 若必须退回 `Ctrl+C`：
  - 进入一次性的“内部选择会话”
  - 会话期间，剪贴板轮询线程必须忽略这次变化
  - 恢复原剪贴板后再退出会话

### 决策 3：为历史页和文件剪贴板补运行期诊断

原则：

- 不再只看“代码好像绑定了”。
- 必须给关键点击链和关键写入链加最小诊断：
  - 点击到了哪里
  - 回调是否触发
  - 文件路径是否存在
  - 剪贴板写入是否成功

## 5. 具体修复阶段

### Phase 1：监听与剪贴板隔离

目标：

- 彻底消除“未点 `GO` 自动生成”
- 降低或消除系统剪贴板被干扰

任务：

1. 为 `simulate_copy()` 引入“内部选择会话 token”
2. 轮询线程发现当前处于内部选择会话时，不把新内容当作外部复制
3. `handle_monitored_text()` 只对真正外部复制触发生成
4. 统一记录：
   - `source`
   - 会话 token
   - 是否直读成功
   - 是否走了 `Ctrl+C` 兜底

重点文件：

- [clipboard.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/clipboard.py)
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)

### Phase 2：双语音状态模型迁移

目标：

- 让 `A` 永远稳定对应“声音列表 1”
- 让 `B` 永远稳定对应“声音列表 2”

任务：

1. 新增稳定字段：
   - `selected_voice_left`
   - `selected_voice_right`
2. 启动迁移旧字段
3. 首页选择逻辑改为：
   - 左侧列表选中只更新 `left`
   - 右侧列表选中只更新 `right`
4. 划词双语音逻辑改为：
   - `A -> left`
   - `B -> right`
5. 如果某侧未选中：
   - 不默默回退到默认声音
   - 直接提示该槽位尚未配置

重点文件：

- [settings.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/config/settings.py)
- [home_view.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/ui/home_view.py)
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)

### Phase 3：修复“复制后生成音频”

目标：

- 用户手动 `Ctrl+C` 后，只要开启该模式，就应稳定生成并按设置朗读

任务：

1. 明确“外部复制”和“内部划词复制”的判定边界
2. 对手动 `Ctrl+C` 做稳定去抖，避免一份文本被重复生成
3. 为该模式补一条单独的诊断日志
4. 修复 UI 文案显示异常

重点文件：

- [clipboard.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/clipboard.py)
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
- [settings_view.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/ui/settings_view.py)

### Phase 4：修复历史页交互

目标：

- 播放、删除、清空全部在真实 EXE 中可靠可用

任务：

1. 给 `HistoryView` 的三个入口加日志
2. 给 `main.py` 的三个历史回调加日志
3. 验证：
   - 点击是否触发
   - 记录 `path` 是否存在
   - 删除是否被文件锁阻塞
4. 如有必要：
   - 为历史项改用更明确的按钮布局
   - 避免容器层或焦点层吞掉点击

重点文件：

- [history_view.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/ui/history_view.py)
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)
- [history.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/history.py)

### Phase 5：修复 MP3 文件剪贴板

目标：

- 生成完成后，系统剪贴板中确实能粘贴出一个 MP3 文件

任务：

1. 为文件剪贴板写入结果增加独立验证
2. 若 `CF_HDROP` 简化写法不稳定，则改为显式构造完整文件拖放数据
3. 确保写入动作不会被后续剪贴板恢复逻辑覆盖
4. 只在生成真正成功后写入文件剪贴板

重点文件：

- [files.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/core/files.py)
- [main.py](/D:/软件编写/Anki-TTS-Edge/Anki-TTS-Flet/main.py)

## 6. 验证矩阵

### 划词单语音模式

- 框选文本但不点 `GO`
  - 不应自动生成
- 点 `GO`
  - 只生成一次
  - 按自动播放设置决定是否朗读
- 框选后，系统原剪贴板内容保持不变

### 划词双语音模式

- 框选文本后出现 `A / B`
- 点 `A`
  - 必须使用声音列表 1 的声音
- 点 `B`
  - 必须使用声音列表 2 的声音
- 不点击按钮时不得自动生成

### 复制后生成音频

- 手动 `Ctrl+C`
  - 只生成一次
  - 不被划词模式抢走
- 自动播放开启时应立即朗读
- 自动播放关闭时只生成不朗读

### 历史页

- 点播放
  - 能播放对应记录
- 点删除
  - UI 消失
  - 文件被删除
- 点清空全部
  - 列表清空
  - 文件清空

### MP3 文件剪贴板

- 生成成功后，在资源管理器或桌面执行粘贴
  - 能粘贴出对应 MP3 文件
- 关闭该选项后
  - 不应再把 MP3 放进剪贴板

## 7. 执行顺序建议

推荐顺序：

1. `Phase 1` 监听与剪贴板隔离
2. `Phase 2` 双语音状态模型迁移
3. `Phase 3` 修复“复制后生成音频”
4. `Phase 4` 修复历史页交互
5. `Phase 5` 修复 MP3 文件剪贴板
6. 重建 `dist/`
7. 做受控 EXE 冒烟
8. 再让用户做一次集中验收

## 8. 当前结论

这 6 个问题里，最核心的不是单个按钮失效，而是两条基础设计没有彻底收口：

- 划词内部复制与外部复制监听仍然耦合
- 双语音状态仍然用“latest / previous”而不是稳定的“列表 1 / 列表 2”槽位

只要这两件事不改，后面就会继续出现：

- 未点 `GO` 自动生成
- `A / B` 对错声音
- 剪贴板被干扰
- `Ctrl+C` 模式时好时坏

后续修复必须优先从这两个根因下手，而不是继续零碎热修。
