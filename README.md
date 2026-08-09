# Anki-TTS-Edge

<div align="center">

一款面向 Anki 制卡、语言学习和文章朗读的 Windows 语音生成工具。

支持 Microsoft Edge 在线语音、本地 Kokoro、双声音、划词/复制触发、历史记录和系统托盘。

[English](README-EN.md) · [下载最新版](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest)

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/EllisMorrow/Anki-TTS-Edge)](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest) [![GitHub last commit](https://img.shields.io/github/last-commit/EllisMorrow/Anki-TTS-Edge)](https://github.com/EllisMorrow/Anki-TTS-Edge/commits/master) [![GitHub All Releases Downloads](https://img.shields.io/github/downloads/EllisMorrow/Anki-TTS-Edge/total?label=Downloads&color=brightgreen)](https://github.com/EllisMorrow/Anki-TTS-Edge/releases)

</div>

## 软件界面

<div align="center">
  <img alt="image" src="https://github.com/user-attachments/assets/b6cef667-c01c-4b27-b00a-fcdd77e0f302" />
</div>

> 软件主界面：可选择声音、输入文本、生成和播放音频。

## 核心功能

- **在线与离线双引擎**：默认使用 Microsoft Edge 在线语音，也可安装本地 Kokoro 引擎。
- **双声音槽位**：声音列表 1 / 2 分别对应 `A / B`，适合对比发音或制作双语音卡片。
- **划词与复制触发**：可通过复制文本或 Windows 划词快速生成语音。
- **同步朗读与点读**：在线语音支持时间戳高亮、上一句/下一句和精确跳播；离线语音通过重新合成实现点读。
- **音频文件到剪贴板**：生成后可将 MP3 文件直接粘贴到 Anki 等应用。
- **历史记录与清理**：可以回听、删除或清空历史，并回收应用生成的孤立音频。
- **桌面集成**：支持系统托盘、窗口置顶、自动播放以及深色/浅色主题。
- **中英文界面**：界面语言可随时切换，设置会自动保存。

## 下载与运行

### 方式一：下载 Windows 版本（推荐）

1. 打开 [Releases](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest)。
2. 下载 `Anki-TTS-Edge-v2.9.3-windows-amd64.zip`。
3. 完整解压 ZIP，然后运行 `Anki-TTS-Edge.exe`。

> 请保留解压后的完整文件夹，不要只单独移动 EXE。

### 方式二：从源码运行

环境要求：Windows、Python 3.10 或更高版本。

```powershell
git clone https://github.com/EllisMorrow/Anki-TTS-Edge.git
cd Anki-TTS-Edge
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Anki-TTS-Flet\requirements.txt
.\.venv\Scripts\python.exe Anki-TTS-Flet\main.py
```

## 使用方法

1. **选择引擎**：默认使用在线 Edge TTS；需要离线语音时，可在设置中切换到本地 Kokoro。
2. **选择声音**：单声音使用声音列表 2；双声音模式下，`A` 使用声音列表 1，`B` 使用声音列表 2。
3. **生成音频**：输入或粘贴文本，然后点击生成按钮。是否自动播放、是否复制 MP3 可在设置中控制。
4. **复制或划词生成**：启用对应监听选项后，复制文本或在 Windows 中划词，再通过悬浮按钮选择 `GO / A / B`。
5. **播放与点读**：在线模式可高亮跟随、跳句或点击文本跳播；离线模式点击文本后会从相应位置重新合成。
6. **管理历史**：在“历史”页回听或删除记录；“清空全部”会同时清理关联音频。
7. **安装离线引擎**：在“设置 → 语音引擎”中选择离线模式，点击“自动下载并安装”，完成后可重新校验。

用户设置、历史、音频和可选离线引擎统一存放在：

```text
%APPDATA%/Anki-TTS-Edge/
```

## v2.9.3 更新内容

- 加固离线引擎的下载、SHA-256 校验、安全解压、manifest 信任边界和卸载范围。
- 设置、历史和声音缓存改为原子写入；历史删除被限制在应用音频目录内。
- 深度清理支持本地引擎 WAV，并修正离线缓存身份。
- 使用全新的抗锯齿三色圆形图标，包含 1024px 源图和九种 Windows ICO 尺寸。
- 补全 GPL-3.0-only、第三方 NOTICE、依赖固定、Windows CI 和 Dependabot。
- Flet / flet-desktop 暂时保留在已经验证的 0.28.3，后续大版本需要专项迁移。

完整记录见 [CHANGELOG.md](CHANGELOG.md)。

## 开发与构建

### 技术栈

| 模块 | 技术 |
|---|---|
| 桌面界面 | Flet / Flutter |
| 在线语音 | edge-tts |
| 本地语音 | Kokoro + sherpa-onnx 边车 |
| 音频播放 | pygame |
| Windows 集成 | pywin32、pynput、pystray、pyperclip |
| 图像与托盘 | Pillow |

### 项目结构

```text
Anki-TTS-Edge/
├── .github/              # CI 与 Dependabot
├── Anki-TTS-Flet/
│   ├── assets/           # 图标、翻译和本地引擎 manifest
│   ├── config/           # 常量与用户设置
│   ├── core/             # TTS、播放、监听、历史和离线引擎
│   ├── ui/               # Flet 页面与控件
│   ├── utils/            # 通用工具
│   ├── main.py           # 程序入口
│   └── requirements.txt  # 固定的直接依赖
├── tests/                # 回归测试
├── tools/                # 运行时自检工具
├── Anki-TTS-Edge.spec    # PyInstaller 构建配置
├── ARCHITECTURE.md       # 架构与维护约束
└── CHANGELOG.md          # 版本更新记录
```

### 构建 Windows 程序

项目使用 PyInstaller `onedir` 模式。不要改成 `onefile`，否则会增加启动等待和杀毒软件扫描概率。

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe -y --clean Anki-TTS-Edge.spec
```

构建结果位于 `dist/Anki-TTS-Edge/`，其中 `Anki-TTS-Edge.exe` 是程序入口。发布时必须保留完整目录以及同级的 `LICENSE`、`NOTICE`。

### 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv\Scripts\python.exe tools\flet_runtime_selfcheck.py
.\.venv\Scripts\python.exe -m compileall -q Anki-TTS-Flet scripts tools
```

更多维护信息：

- [ARCHITECTURE.md](ARCHITECTURE.md)：运行链路、状态边界和安全约束。
- [MAINTENANCE.md](MAINTENANCE.md)：Python、依赖和 Flet 升级策略。
- [CHANGELOG.md](CHANGELOG.md)：完整版本记录。

## 许可与第三方服务

Anki-TTS-Edge 按 [GPL-3.0-only](LICENSE) 发布，第三方组件说明见 [NOTICE](NOTICE)。

本软件不是微软官方产品。使用 Microsoft Edge TTS 或其他第三方服务时，用户应遵守适用法律和相应服务条款；第三方服务条款不改变本项目的开源许可证。

本软件按“原样”提供，不附带任何明示或暗示担保。用户应自行评估下载、安装和使用风险。

<div align="center">

Made with ❤️ for Language Learners

</div>
