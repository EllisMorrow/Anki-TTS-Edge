# Anki-TTS-Edge

**[English Documentation](https://github.com/msjsc001/Anki-TTS-Edge/blob/master/README-EN.md)**

<div align="center">

Anki-TTS-Edge 是一个基于微软 Edge TTS 技术的免费、高质量语音生成工具，它**能快速的通过划选后生成音频**，开启双音频（双点）模式后能选择两种不同的语音生成音频，生成音频后能自动复制到剪贴板，快速的粘贴到 Anki 之类的软件使用。也能作为**语言学习、文章阅读的便捷朗读工具**使用。
**全新 v2.0 版本已使用 Flet (Flutter) 框架完全重构**，带来更现代化的 UI、更流畅的动画和更强大的功能体验。

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/msjsc001/Anki-TTS-Edge)](https://github.com/msjsc001/Anki-TTS-Edge/releases/latest) [![GitHub last commit](https://img.shields.io/github/last-commit/msjsc001/Anki-TTS-Edge)](https://github.com/msjsc001/Anki-TTS-Edge/commits/master) [![GitHub All Releases Downloads](https://img.shields.io/github/downloads/msjsc001/Anki-TTS-Edge/total?label=Downloads&color=brightgreen)](https://github.com/msjsc001/Anki-TTS-Edge/releases)

</div>

## 🔄 最新稳定化更新（v2.9.2）

- **修复换声音后仍播放旧音频**：播放/朗读的缓存判定现在会包含 `引擎 + 声音/音色(sid) + 语速/音量/音高 + 文本`，切换声音后再次播放会自动重新生成。
- **离线点读恢复（通过重新合成）**：离线 Kokoro 无时间戳时仍会显示可点击文本层；点击某字/词会停止当前播放并从该位置开始重新生成后朗读（不写入历史、不复制剪贴板）。
- 离线模式 V1 说明：`timestamps` 仍为空（不支持逐词高亮跟随/毫秒级跳播与跳句 seek），但点读可用（通过重新合成实现）；长文本会自动禁用点读层以保证性能。
- 离线模式下的“声音列表”使用 Kokoro 官方音色目录（sid 分组：中(男/女)、英(女)、美(女)），并提供“离线语音音效听”跳转到官方试听页。
- 引擎切换时会停止播放并清空当前音频状态，避免“切在线但还在播离线旧音频”的错觉；切换后提示需重新生成。
- Edge 在线生成失败时界面会显示更具体的失败原因（便于定位网络/voice/服务端问题），并对常见“文本语言与 voice locale 不匹配”给出中文可理解提示。
- 划词/复制触发生成加入忙时断路器，避免反复触发造成卡死和高占用。

## ✨ 核心特性

- **全新现代化 UI**：基于 Flet (Flutter) 重构，界面美观、响应迅速，支持深色/浅色主题切换。
- **海量语音库**：免费集成 300+ 个微软 Edge 神经网络语音，覆盖数十种语言和地区口音。
- **高亮跟随朗读**：朗读时单词实时高亮，精确同步，支持 "1"->"one" 等复杂符号映射。
- **即点即读**：朗读模式下，点击文段中任意单词/字符，立即从该位置精确播放。
- **智能导航**：支持"上一句/下一句"跳转，方便逐句校对学习。
- **双语音模式**：稳定的双声音槽位配置，可快速在两种不同声音（如一男一女、英音美音）间切换或生成。
- **历史记录管理**：自动保存生成历史，支持随时回听、删除与清空；深度清理回收孤立文件。
- **智能监控**：
  - **复制后生成音频**：复制文本后即可自动生成，并可按设置直接朗读。
  - **划词单/双语音模式**：(Windows) 划词后通过 `GO / A / B` 快速决定生成方式。
- **离线语音引擎（可选）**：设置页一键安装/校验/卸载并切换到本地 Kokoro（sidecar 下载，不增加主程序体积）。
- **贴心功能**：
  - **系统托盘**：支持最小化到托盘，后台静默运行。
  - **窗口置顶**：钉在桌面最上层，方便配合 Anki 或浏览器使用。
  - **多语言界面**：原生支持中文和英文界面，实时切换。
  - **用户数据集中管理**：所有数据存储在 `%APPDATA%/Anki-TTS-Edge/`，干净整洁。


## 📸 界面展示

<div align="center">
  <img alt="image" src="https://github.com/user-attachments/assets/b6cef667-c01c-4b27-b00a-fcdd77e0f302" />
</div>

> *注：全新 Flet 界面，简洁直观*

## 🚀 安装与运行

### 环境要求
- Python 3.8 或更高版本
- Windows 系统 (建议，以获得完整的划词监控支持)

### 快速开始

1. **克隆项目**
   ```bash
   git clone https://github.com/msjsc001/Anki-TTS-Edge.git
   cd Anki-TTS-Edge
   ```

2. **安装依赖**
   ```bash
   pip install -r Anki-TTS-Flet/requirements.txt
   ```
   *注意：如果尚未生成 requirements.txt，可手动安装核心依赖：*
   ```bash
   pip install flet==0.28.3 flet-desktop==0.28.3 edge-tts pygame pyperclip pynput pystray pillow pywin32
   ```

3. **运行程序**
   ```bash
   python Anki-TTS-Flet/main.py
   ```

## 👨‍💻 开发者指南

欢迎开发者参与 Anki-TTS-Edge 的开发与定制！以下是项目的核心架构与开发指南：

### 技术栈
* **UI 框架**: Flet (基于 Flutter 的 Python 现代化 UI 框架)，提供响应式设计和流畅动画。
* **核心 TTS**: `edge-tts` (微软 Edge 神经网络语音接口的非官方实现)。
* **音频与多媒体**: `pygame` (提供低延迟、稳定的多线程音频播放机制)。
* **系统交互**: `pyperclip` (剪贴板监听)、`pystray` / `pillow` (系统托盘驻留)。
* **异步与并发**: 深度使用 `asyncio` 进行异步 I/O 控制，确保 UI 线程在网络请求和音频生成时绝不卡顿。

### 开发核心技术点解析
1. **字幕级高亮对齐 (Text-to-Speech Alignment)**
   利用 `edge-tts` 字典和时间戳，结合 Flet 的 `TextSpan` 和 `TextStyle` 在音频播放回调中动态重绘文本区块背景颜色，达到“卡拉OK”式的精准单词同步。
2. **全局输入/剪贴板监听器 (Background Monitor)**
   后台常驻轮询线程自动检测系统剪贴板变化（或光标选中文本）。检测到变化时，立即触发并提升应用窗口 (Bring to Front) 至最顶层，彻底节省了制卡时繁琐的复制粘贴点击步骤。
3. **音频状态与垃圾回收 (Garbage Collection)**
   在历史记录管理模块实现了防泄漏的垃圾回收机制，使用哈希和路径跟踪音频和元数据 (.json)；在清理操作时遍历本地真实文件列表以剔除“孤儿”（Orphaned）文件。
4. **组件化与状态共享设计**
   UI 被拆分为独立的路由视图 (首页、历史记录、设置)，相互之间通过全局状态管理器或配置注入进行低耦合通信。

### 📂 项目结构

```text
Anki-TTS-Edge/
├── ARCHITECTURE.md      # 架构决策、运行链路与维护记忆
├── Anki-TTS-Flet/       # 主程序核心源码目录
│   ├── assets/          # 图标、本地化翻译文件等静态资源
│   ├── config/          # 默认配置定义及用户配置读写逻辑
│   ├── core/            # 业务逻辑大脑 (TTS 引擎操作, 时间戳对齐, 全局监听器, 历史纪录 IO)
│   ├── ui/              # Flet 页面组件视图 (分模块的UI页面及定制组件)
│   ├── utils/           # 通用工具函数 (文件操作, 文本格式化等)
│   └── main.py          # 程序入口与初始化挂载
├── .gitignore           # Git 忽略文件规则
└── README.md            # 项目文档
```

### 🔨 构建可执行文件 (EXE)

如需针对 Windows 构建独立的可执行程序，我们采用 PyInstaller **文件夹模式 (onedir)** 进行打包：

> ⚠️ **重要提示**：请勿使用 `--onefile` 模式。单文件模式会导致 Windows 下启动极慢（每次运行时需解压全部文件到临时目录，且容易触发杀毒软件扫描）。

```bash
# 请确保在虚拟环境中安装了 pyinstaller
pip install pyinstaller

# 根目录执行以下打包命令（文件夹模式，推荐使用仓库内的 .spec）
.\.venv\Scripts\pyinstaller.exe -y --clean Anki-TTS-Edge.spec
```

构建完成后，`dist/Anki-TTS-Edge/` 目录即为完整的可发布程序，其中 `Anki-TTS-Edge.exe` 为入口文件。

## 📑 使用指南

1. **选择声音**：在首页顶部下拉框选择语言和具体发音人。
2. **生成音频**：输入或粘贴文本，点击 **蓝色按钮** 开始生成。
   - **左侧按钮**：使用"语言 (左)"的配置。
   - **右侧按钮**：使用"语言 (右)"的配置。
3. **复制文件**：生成中显示绿色，完成后变为红色。点击红点或按 **Ctrl+C** 即可复制音频文件路径（可直接粘贴到 Anki）。
4. **查看历史**：切换到頂部 **"历史"**页签，查看过往生成记录。
5. **偏好设置**：在 **"设置"**页签中自定义外观（深色模式）、行为（自动播放、最小化到托盘）等。
   - 如需离线模式：在“语音引擎”中切换为离线，并点击“自动下载并安装”。安装后可点击“重新校验”确认可用。

---
<div align="center">
Made with ❤️ for Language Learners
</div>

---

## 📋 更新日志

详见 [CHANGELOG.md](CHANGELOG.md)

---

## ⚠️ 免责声明

本项目（Anki-TTS-Edge）仅供个人学习、研究和学术交流使用。

1.  **非商业用途**：本软件并非微软官方产品，基于开源社区代码修改而来。使用本软件产生的任何音频文件仅限个人使用，严禁用于任何商业用途或公开传播。
2.  **免责条款**：
    *   本软件按“原样”提供，不提供任何形式的明示或暗示担保，包括但不限于适销性、特定用途适用性和非侵权性担保。
    *   **在任何情况下，开发者（及贡献者）均不对因使用或无法使用本软件而引起的任何直接、间接、偶然、特殊、惩罚性或后果性损害（包括但不限于数据丢失、业务中断、计算机故障等）承担责任，无论这些损害是基于合同、侵权（包括疏忽）或其他法律依据，也无论开发者是否已被告知此类损害的可能性。**
    *   用户应自行承担下载、安装和使用本软件的所有风险。
3.  **合规性**：用户在使用本软件时，必须遵守当地法律法规及微软相关服务条款。任何因违反法律法规或服务条款而导致的法律责任，概由用户自行承担。

**下载或使用本软件即表示您已阅读并同意上述所有条款。如果您不同意，请立即停止使用并删除本软件。**
