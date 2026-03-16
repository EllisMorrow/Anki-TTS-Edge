# Anki-TTS-Edge 恢复计划

更新时间：2026-03-13

## 当前阶段进度

- `Phase 1` 已基本完成：
  - 主界面可以稳定启动
  - `surface_variant`、只读 `page`、`Dropdown`、按钮构造等启动级 Flet 兼容问题已清掉
- 新一轮功能修复已进入联调：
  - 设置语义已拆分为“复制后生成音频 / 鼠标划选生成音频 / 双语音模式 / 划词双语音模式”
  - `main.py` 已从旧 `dual_blue_dot_enabled` 迁移到新字段
  - 剪贴板复制现在会走统一生成入口，而不是只把文本塞进输入框
  - 生成完成后的 MP3 文件剪贴板写入已加监听抑制
  - 历史页外层吞事件与清空对话框链路已修
- 当前唯一阻塞不是代码，而是打包替换：
  - `dist/Anki-TTS-Edge/Anki-TTS-Edge.exe` 正在运行中
  - PyInstaller 可以完成分析、打包、链接 EXE，但在覆盖 `dist/` 现有产物时因文件锁失败
  - 需要先关闭正在运行的 `dist` 版 EXE，才能把最新代码重新落到唯一 `dist/`

## 1. 文档用途

本文件用于在当前聊天窗口失效、上下文丢失或换新窗口继续时，作为唯一的恢复入口。

目标：

- 记录项目当前真实状态。
- 解释“为什么原本能跑，修完后反而启动报错”。
- 固化已经确认的技术结论与证据。
- 给出一套可执行、可交接、可验证的完整修复计划。
- 避免下一位接手者继续走“修一个报错，打一个坏包”的错误路径。

配套必读文件：

- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `Anki-TTS-Flet/main.py`
- `Anki-TTS-Flet/ui/home_view.py`
- `Anki-TTS-Flet/ui/history_view.py`
- `Anki-TTS-Flet/ui/settings_view.py`
- `Anki-TTS-Edge.spec`
- `Anki-TTS-Flet/requirements.txt`

## 2. 当前结论

当前问题不是单个业务 Bug，而是 `Flet` 运行时版本与项目 UI 代码 API 严重错位。

现状可以归纳为三句话：

- 项目历史上从未锁定一个已验证可运行的 `Flet` 版本。
- 代码本身混用了多代 `Flet API`，不是一套单一版本的写法。
- 之前为了修 EXE 缺少 `flet_desktop`，把运行时锁到了 `flet==0.82.2`，从而把长期潜伏的 UI 兼容问题全部引爆。

因此：

- `dist281`、`dist282`、`dist283` 都不是可发布构建。
- 它们失败的原因是连续暴露的同一条兼容性问题链，不是三个互不相关的事故。
- 继续赌旧版依赖不可控，应该直接做一次完整的 `Flet 0.82.2` UI 兼容迁移。

## 3. 项目背景

### 3.1 产品定位

这是一个基于 `Flet` 的 Windows 桌面 TTS 工具，核心流程是：

- 文本输入
- 语音列表选择
- `edge-tts` 生成音频与词级时间戳
- `pygame` 播放
- 历史记录回放
- 托盘、卫星窗、剪贴板/划词监听

用户数据统一存储在 `%APPDATA%/Anki-TTS-Edge/`。

### 3.2 本轮已完成且应保留的业务修复

这批修复与当前 `Flet` 启动问题是两条线，原则上应该保留，不应因为 UI 迁移被回退：

- 补齐启动依赖：`pynput`、`pywin32`
- 托盘/卫星恢复主窗口统一改到 `page.window.*`
- 音频文件名改为“微秒时间戳 + 短 UUID”，避免秒级重名覆盖
- 历史回放时同步刷新文本与时间戳，避免串音
- 历史超上限时同步删除被淘汰音频与时间戳文件
- 主题持久化统一为 `appearance_mode`
- 剪贴板监听与划词监听解耦
- 播放监控改为单实例，减少并发竞态
- 历史字段兼容旧数据格式

这些修改主要分布在：

- `Anki-TTS-Flet/core/audio_gen.py`
- `Anki-TTS-Flet/core/history.py`
- `Anki-TTS-Flet/config/settings.py`
- `Anki-TTS-Flet/main.py`
- `Anki-TTS-Flet/ui/history_view.py`
- `Anki-TTS-Flet/ui/settings_view.py`
- `Anki-TTS-Flet/assets/translations.json`

## 4. 问题是如何被引爆的

### 4.1 原始打包问题

最早的 EXE 启动失败，是因为包里缺少 `flet_desktop`，错误为：

- `ModuleNotFoundError: No module named 'flet_desktop'`

为修这个问题，后续做了两件事：

- 在 `requirements.txt` 中加入并固定 `flet==0.82.2` 与 `flet-desktop==0.82.2`
- 在 `Anki-TTS-Edge.spec` 中显式收集 `flet_desktop`

这一步解决了“缺模块”，但没有先验证“当前项目 UI 是否真的兼容 0.82.2”。

### 4.2 为什么修完后程序反而废了

原因不是业务逻辑被整体改坏，而是启动过程在 UI 框架层连续撞上 API 不兼容：

1. `ColorScheme.surface_variant` 在当前实际运行面上不兼容
2. 三个视图类把 `self.page` 当普通实例属性写入，而当前 `Flet Control` 基类把它当只读属性
3. `Tabs/Tab/Dropdown/Button/alignment` 这批 API 和当前 `flet==0.82.2` 导出的真实签名不一致

这就导致：

- 修掉一个启动报错后，只会继续暴露下一个兼容问题
- 如果不做整体验证，只靠一个报错一个报错地打包，会连续产出坏包

## 5. 已确认的技术证据

### 5.1 依赖历史

历史上项目长期只有宽松依赖：

```txt
flet>=0.21.0
```

仓库中没有以下任何一种“可复现环境”文件：

- `poetry.lock`
- `Pipfile.lock`
- `pyproject.toml`
- 版本锁定脚本
- 成功发布所用的 `Flet` 版本记录

这意味着项目一直依赖“当时机器环境恰好可跑”。

补充确认：

- 项目本地 `.venv` 中实际安装的是 `flet 0.28.3`
- 这基本可以解释“为什么之前开发机上它能跑”
- 当前问题不是业务逻辑突然报废，而是运行时从旧版 `Flet` 漂移到了 `0.82.2` 后，旧 UI 写法被集中引爆

### 5.2 已确认的运行时兼容问题

通过本地真实运行时签名扫描，当前代码与 `flet==0.82.2` 至少有以下构造参数不兼容：

- `Anki-TTS-Flet/main.py`
  - `ft.Tabs(tabs=[...])`
  - `ft.Tab(text=..., content=...)`
- `Anki-TTS-Flet/ui/home_view.py`
  - `ft.Dropdown(..., on_change=...)`
  - `ft.FilledTonalButton(..., text=...)`
  - `ft.FilledButton(..., text=...)`
- `Anki-TTS-Flet/ui/settings_view.py`
  - `ft.Dropdown(..., on_change=...)`
  - `ft.OutlinedButton(..., text=...)`

本地静态兼容扫描结果：

- 构造参数不兼容：15 处
- 缺失符号引用：3 处

缺失符号包括：

- `ft.alignment.top_left`
- `ft.alignment.center`

### 5.3 直接构造视图的探测结果

脱离桌面壳，直接在 Python 中实例化视图后，已确认的首批异常为：

- `HomeView` 失败：`ft.alignment.top_left` 不存在
- `SettingsView` 失败：`Dropdown.__init__() got an unexpected keyword argument 'on_change'`
- `main(fake_page)` 同样首先卡在 `HomeView`

这证明问题不在 PyInstaller，而在代码本身对 `Flet API` 的使用。

### 5.4 兼容垫片探测结果

做了一个仅用于调查的兼容垫片：

- 把 `Dropdown.on_change` 映射到当前运行时的正确事件
- 把旧式 `Button(text=...)` 映射成 `content=ft.Text(...)`
- 把 `Tabs/Tab` 旧接口做临时适配
- 把缺失的 `alignment` 常量临时补齐

结果：

- 启动流程可以继续推进到“加载语音缓存、初始化监听器、启动托盘”
- 没有再出现新的启动级崩溃

这说明当前主阻塞是“`Flet UI API` 错位”，而不是业务链路整体损坏。

### 5.5 新确认的打包问题

在完成 UI 兼容第一轮迁移后，新的 EXE 报错为：

- 缺少 `..._internal\\flet\\controls\\material\\icons.json`

这说明：

- 打包时不仅要收集 `flet_desktop`
- 还必须收集 `flet` 包本身的数据文件
- 否则应用虽然能走到更后面的启动阶段，但会在读取图标元数据时失败

当前处理原则：

- `.spec` 中同时 `collect_all('flet')`
- `.spec` 中同时 `collect_all('flet_desktop')`
- README 构建命令也必须同步包含 `--collect-all flet`

## 6. 当前工作树状态

截至本文件写入时，工作区包含未提交修改，主要集中在：

- `.gitignore`
- `ARCHITECTURE.md`
- `Anki-TTS-Edge.spec`
- `Anki-TTS-Flet/config/constants.py`
- `Anki-TTS-Flet/main.py`
- `Anki-TTS-Flet/requirements.txt`
- `Anki-TTS-Flet/ui/history_view.py`
- `Anki-TTS-Flet/ui/home_view.py`
- `Anki-TTS-Flet/ui/settings_view.py`
- `CHANGELOG.md`
- `README.md`
- `README-EN.md`

说明：

- 这些修改包含正确修复，也包含未完成的 UI 兼容迁移尝试。
- 当前状态不能直接打正式发布。
- 不应把当前状态直接推送到 GitHub Release。

## 7. 当前构建目录说明

以下目录都属于调查过程中的实验性构建，不可发布：

- `dist281`
- `dist282`
- `dist283`
- `dist284`

已知情况：

- `dist281`：主要暴露 `flet_desktop` 缺失问题
- `dist282`：开始暴露主题与 UI API 兼容问题
- `dist283`：继续暴露 UI API 兼容问题
- `dist284`：UI 兼容首轮修复后，继续暴露 `flet` 数据文件未打包的问题

规则：

- 不要再让用户测试 `dist281/282/283`
- 下一次测试必须使用新的独立输出目录，例如 `dist284` 或 `dist_flet0822`
- 每次重建必须配套新的 `build*` 目录，避免旧文件锁或残留干扰

## 8. 决策记录

### 8.1 已放弃方案：回猜旧版 Flet

不选它的原因：

- 没有“最后已知可运行”的版本记录
- 当前代码已经混用多代 API，降级不一定能一次对齐
- 继续靠猜版本，时间会耗在环境试错上，不会得到稳定的长期解

### 8.2 已选方案：完整迁移到 `flet==0.82.2`

这是当前最稳的路线。

原因：

- 当前打包链已经需要 `flet_desktop`
- 当前运行时已可稳定复现 API 差异
- 兼容面已被静态扫描和调查脚本明确抓出
- 主业务逻辑仍在，问题集中在 UI 层

## 9. 完整修复计划

### Phase 0：冻结坏包与建立基线

目标：

- 停止继续让用户测试已知坏包
- 固定本次修复的唯一目标版本：`flet==0.82.2`、`flet-desktop==0.82.2`
- 以当前调查结论建立后续执行基线

任务：

- 保留本文件与 `ARCHITECTURE.md`
- 将 `dist281/282/283` 标记为废弃实验包
- 不推送当前脏工作树
- 在继续编码前，明确“只做 0.82.2 兼容迁移，不再切换 Flet 版本”

退出条件：

- 接手者理解当前失败原因不是业务逻辑，而是 UI API 错位
- 接手者知道当前 `dist/` 覆盖失败的直接原因是目标 EXE 正在运行，不要误判为 PyInstaller 或代码错误

### Phase 1：主启动链 UI API 迁移

目标：

- 让程序从 EXE 启动后，稳定进入主界面

重点修改文件：

- `Anki-TTS-Flet/main.py`
- `Anki-TTS-Flet/ui/home_view.py`
- `Anki-TTS-Flet/ui/settings_view.py`
- `Anki-TTS-Flet/ui/history_view.py`

必须完成的事项：

1. `Tabs/Tab` 全量迁移
   - 把旧式 `tabs=[...]` / `text=` / `content=` 写法改成当前 `Flet 0.82.2` 兼容写法
   - 避免临时兼容垫片进入正式代码

2. `Dropdown` 事件迁移
   - 将 `on_change` 替换为当前运行时正确事件
   - 校验左右语言筛选与设置页语言切换都还能正常触发

3. 按钮构造迁移
   - 把 `FilledButton` / `FilledTonalButton` / `OutlinedButton` 的 `text=` 改为当前兼容写法
   - 检查按钮文本更新逻辑不受影响

4. 对齐常量迁移
   - 去掉 `ft.alignment.top_left` / `ft.alignment.center` 等不存在的符号
   - 改用当前版本明确支持的 `Alignment(...)` 或等价写法

5. 主题构造收敛
   - 保留目前已做的“兼容构造”思路
   - 确认主题在浅色/深色模式下都能创建成功

6. 控件生命周期收敛
   - 检查是否有“控件未挂到页面前就调用 `update()`”的路径
   - 对真正存在的问题做延后更新或统一刷新

退出条件：

- `python Anki-TTS-Flet/main.py` 能稳定拉起，不出现 Flet 错误页
- 主窗口至少能显示 3 个主标签页和基础控件

### Phase 2：页面级功能回归

目标：

- 在源码运行模式下恢复核心功能可用

必测范围：

1. 主页
   - 文本输入
   - 左右语言筛选
   - 语音列表刷新
   - 生成 A/B 音频
   - 播放、暂停、停止
   - 高亮文本显示

2. 历史页
   - 历史记录显示
   - 点击历史回放
   - 删除单项
   - 清空全部

3. 设置页
   - 主题切换
   - 语言切换
   - 自动播放
   - 剪贴板监听
   - 划词监听
   - 双蓝点
   - 托盘开关
   - 窗口大小保存

退出条件：

- 三个主页面均可正常打开和交互
- 无新的启动级兼容异常

### Phase 3：Windows 集成功能验证

目标：

- 确认不是只有 UI 能开，而是 Windows 相关功能也能继续使用

必测范围：

- 最小化到托盘
- 托盘恢复主窗口
- 卫星窗启动/唤起主窗口
- 剪贴板监控
- 划词监控
- 双蓝点模式
- `%APPDATA%/Anki-TTS-Edge` 数据读写

注意：

- 这一阶段才去碰 `pystray`、`pynput`、卫星窗进程
- 如果这里失败，先修系统集成，不要提前发包

退出条件：

- 托盘、卫星窗、监听链路至少完成一轮真实手工验证

### Phase 4：EXE 打包与发布前验证

目标：

- 产出新的可测试 EXE

任务：

1. 使用新的输出目录打包
   - 示例：`dist284` / `build284`

2. 验证打包完整性
   - `flet_desktop` 已收集
   - `_internal` 完整
   - 无启动即崩

3. EXE 冒烟
   - 启动 10 秒不崩
   - 主进程常驻
   - 主界面可见

4. 至少执行一轮主功能手工验证
   - 不是只看“窗口能打开”

退出条件：

- 仅当源码运行和打包运行都通过后，才允许让用户测试新包

### Phase 5：发布收口

目标：

- 清理实验性输出，整理正式版本，替换损坏发布

任务：

- 更新 `CHANGELOG.md`
- 更新版本号
- 更新 `README.md` / `README-EN.md`
- 确认 `.gitignore` 不会把构建产物和用户数据推上去
- 仅上传最终验证通过的 zip 包

## 10. 详细任务清单

以下清单是下一轮执行时应该逐项勾掉的内容。

### 10.1 `main.py`

- [ ] 按 `Flet 0.82.2` 重写标签页创建方式
- [ ] 清理旧式 `Tab(text=..., content=...)`
- [ ] 保留并验证 `page.window.*` 新接口
- [ ] 保留主题兼容构造
- [ ] 检查 `page.add(...)` 前后的更新时机
- [ ] 验证语言切换后的标签页文本更新链路

### 10.2 `ui/home_view.py`

- [ ] 替换不存在的 `ft.alignment.*` 常量
- [ ] 迁移两个 `Dropdown` 的事件写法
- [ ] 迁移生成按钮写法
- [ ] 检查 `surfaceVariant` 等主题颜色字符串是否兼容当前运行时
- [ ] 检查所有 `update()` 调用是否发生在控件已挂页之后

### 10.3 `ui/settings_view.py`

- [ ] 迁移语言下拉框事件
- [ ] 迁移若干 `OutlinedButton` 的按钮构造方式
- [ ] 保留 `self._host_page` 私有页面引用，不再写 `self.page`
- [ ] 验证主题切换、语言切换、保存设置回调链路

### 10.4 `ui/history_view.py`

- [ ] 保留 `self._host_page`
- [ ] 验证对话框打开/关闭流程
- [ ] 验证历史记录渲染的颜色/布局不会触发新兼容问题

### 10.5 其它

- [ ] 检查 `translations.json` 是否需要补充因按钮构造变化而改动的文本
- [ ] 检查 `README` 中安装与构建命令是否与最终结果一致
- [ ] 检查 `.spec` 与 `requirements.txt` 是否保持同步

## 11. 回归验证矩阵

正式重新给用户测试前，至少完成以下验证：

- [ ] 源码启动成功
- [ ] EXE 启动成功
- [ ] 主页可见且无错误页
- [ ] 设置页可见且语言切换正常
- [ ] 历史页可见
- [ ] 生成音频成功
- [ ] 播放成功
- [ ] 历史回放成功
- [ ] 主题切换后 UI 不报错
- [ ] 托盘最小化/恢复成功
- [ ] 卫星窗唤醒主窗口成功
- [ ] 剪贴板监听可触发
- [ ] 划词监听可触发
- [ ] `%APPDATA%` 写入正常

## 12. 接手时禁止做的事

- 不要继续要求用户测试 `dist281/282/283`
- 不要再切换新的 `Flet` 版本做赌博式尝试
- 不要把“临时兼容垫片”直接当正式实现提交
- 不要在主问题未收敛前继续发布新 Release
- 不要为了“先能跑”回退已经修好的业务 Bug

## 13. 接手时推荐的第一步

如果在新聊天窗口继续，建议顺序如下：

1. 打开本文件与 `ARCHITECTURE.md`
2. 读取 `Anki-TTS-Flet/main.py`、`ui/home_view.py`、`ui/settings_view.py`
3. 直接按 `Flet 0.82.2` 正式 API 重构 `Tabs/Tab/Dropdown/Button/alignment`
4. 跑源码启动验证
5. 跑页面级回归
6. 最后才打 EXE

## 14. 当前信心评估

基于现有调查，当前判断如下：

- 修复后稳定进入主界面：高概率
- 恢复主页/历史/设置三页的主功能：高概率
- 恢复托盘、卫星窗、监听链路：中高概率
- 直接靠继续打补丁式修包成功：低概率

一句话结论：

当前不是“程序已经彻底废了”，而是“项目被长期未锁版本的 `Flet` 依赖漂移击穿了启动层”。正确做法不是继续试错打包，而是完成一次有计划的 `Flet 0.82.2` UI 兼容迁移。

## 15. 2026-03-13 最新状态

本节用于下一聊天窗口直接接手，不需要再回忆上下文。

### 15.1 已确认完成

- `Flet 0.82.2` 启动兼容主线已经打通：
  - 主题兼容构造已落地
  - `page.window.*` 新接口已统一
  - `HomeView / HistoryView / SettingsView` 不再写只读 `page`
  - `Dropdown`、按钮、对齐常量等已迁移到当前可运行写法
- `PyInstaller` 构建链已重新验证：
  - `.spec` 已收集 `edge_tts`、`flet`、`flet_desktop`
  - `icons.json` 缺失问题已修复
  - 统一输出目录已收口为根目录唯一的 `dist/`
- UI 卡顿已经做了第一轮系统性收敛：
  - 顶部三页切换改为单宿主 `view_host`，不再三页常驻 `Stack`
  - 顶部导航尺寸已缩小
  - 托盘改为按需初始化
  - 划词卫星轮询在关闭状态下已降频
  - 剪贴板/划词监听默认按设置惰性启动
  - 语音列表优先本地缓存，只有命中缓存才做后台刷新
  - 长文本播放超过阈值时不再构建大规模逐词高亮控件

### 15.2 2026-03-13 本地验证结果

- `python -m compileall Anki-TTS-Flet` 已通过。
- 新构建已成功生成到：
  - `D:\软件编写\Anki-TTS-Edge\dist\Anki-TTS-Edge\Anki-TTS-Edge.exe`
- 本地做过一次 12 秒启动冒烟：
  - EXE 能拉起
  - 进程保持驻留
  - 未再出现此前的启动级错误页

### 15.3 当前工作区状态

- 旧的 `dist281` 到 `dist286`、`build281` 到 `build286`、`build2` 已全部清理。
- 当前根目录只应保留一个正式输出：
  - `dist/`
- `build/` 已删除。
- 根目录残留一个 `.tmp/`：
  - 内部是 pip 临时缓存
  - 不是项目长期资产
  - 当前因为 ACL/所有权问题未能在沙箱内删净
  - 不影响程序运行，也不应提交到仓库

### 15.4 当前未完成项

- 需要用户基于最新 `dist/` 做真实交互确认：
  - 顶部三页切换延迟是否明显改善
  - “播放/生成音频”按钮的响应是否恢复到可接受范围
- 如果仍有明显延迟，下一步优先排查：
  - `HomeView` 语音列表控件数量是否仍过高
  - 首页 `update()` 是否还存在整树刷新
  - 长文本逐词高亮阈值是否需要继续收紧
  - 是否需要把语音列表进一步改成更轻量的单列/分段渲染

### 15.5 下一窗口接手建议

1. 先读本文件第 15 节和 `ARCHITECTURE.md`
2. 只测试和讨论 `dist/Anki-TTS-Edge/Anki-TTS-Edge.exe`
3. 不要再恢复任何 `dist28x`
4. 如果用户反馈仍卡，优先继续做性能剖面和首页控件树瘦身，不要再去折腾打包链
