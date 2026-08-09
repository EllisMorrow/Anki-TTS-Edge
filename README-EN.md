# Anki-TTS-Edge

<div align="center">

A Windows text-to-speech tool for Anki card creation, language learning, and article reading.

Supports Microsoft Edge online voices, Local Kokoro, dual voices, selection/copy triggers, history, and system tray integration.

[中文文档](README.md) · [Download latest release](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest)

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/EllisMorrow/Anki-TTS-Edge)](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest) [![GitHub last commit](https://img.shields.io/github/last-commit/EllisMorrow/Anki-TTS-Edge)](https://github.com/EllisMorrow/Anki-TTS-Edge/commits/master) [![GitHub All Releases Downloads](https://img.shields.io/github/downloads/EllisMorrow/Anki-TTS-Edge/total?label=Downloads&color=brightgreen)](https://github.com/EllisMorrow/Anki-TTS-Edge/releases)

</div>

## Application Interface

<div align="center">
<img  alt="image" src="https://github.com/user-attachments/assets/c9fade87-7a3f-4ccf-858c-07c2acb6f2e2" />

</div>

> Main application interface for selecting voices, entering text, generating audio, and playback.

## Key Features

- **Online and offline engines**: Use Microsoft Edge online voices by default or install Local Kokoro for offline synthesis.
- **Dual voice slots**: Voice Lists 1 and 2 map consistently to `A / B`, useful for pronunciation comparison and dual-voice cards.
- **Selection and copy triggers**: Generate speech quickly from copied text or Windows text selection.
- **Synchronized reading and point-read**: Online voices support timestamp highlighting, sentence navigation, and precise seeking; offline point-read works through re-synthesis.
- **Audio file clipboard support**: Paste a generated MP3 directly into Anki and other applications.
- **History and cleanup**: Replay, delete, or clear history while reclaiming orphaned application audio.
- **Desktop integration**: Includes system tray, always-on-top, autoplay, and light/dark themes.
- **Chinese and English UI**: Switch the interface language at any time; settings persist automatically.

## Download and Run

### Option 1: Download the Windows package (recommended)

1. Open the [latest Release](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest).
2. Download `Anki-TTS-Edge-v2.9.3-windows-amd64.zip`.
3. Extract the complete ZIP, then run `Anki-TTS-Edge.exe`.

> Keep the extracted folder together. Do not move only the EXE.

### Option 2: Run from source

Requirements: Windows and Python 3.10 or newer.

```powershell
git clone https://github.com/EllisMorrow/Anki-TTS-Edge.git
cd Anki-TTS-Edge
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Anki-TTS-Flet\requirements.txt
.\.venv\Scripts\python.exe Anki-TTS-Flet\main.py
```

## How to Use

1. **Choose an engine**: Edge TTS is the default. Switch to Local Kokoro in Settings when offline synthesis is needed.
2. **Choose voices**: Single-voice mode uses Voice List 2. In dual mode, `A` uses Voice List 1 and `B` uses Voice List 2.
3. **Generate audio**: Enter or paste text, then use a generation button. Autoplay and MP3 clipboard behavior are configurable.
4. **Generate from copy or selection**: Enable the relevant monitor, copy text or select it in Windows, then choose `GO / A / B` from the floating control.
5. **Playback and point-read**: Online mode supports synchronized highlighting, sentence navigation, and text seeking. Offline mode re-synthesizes from the selected position.
6. **Manage history**: Replay or delete entries on the History page. Clear All also removes associated audio.
7. **Install the offline engine**: Select Offline under `Settings → TTS Engine`, click Download & Install, then run Re-validate when installation finishes.

User settings, history, audio, and the optional offline engine are stored under:

```text
%APPDATA%/Anki-TTS-Edge/
```

## What's New in v2.9.3

- Hardened offline-engine downloads, SHA-256 validation, safe extraction, manifest trust, and uninstall boundaries.
- Made settings, history, and voice-cache writes atomic; history deletion is contained to the application audio directory.
- Added generated WAV cleanup and corrected offline cache identity.
- Replaced the pixelated icon with an anti-aliased three-color design, including a 1024px master and nine Windows ICO sizes.
- Completed GPL-3.0-only and third-party notices, pinned direct dependencies, and added Windows CI plus Dependabot.
- Flet and flet-desktop remain on the validated 0.28.3 release until a dedicated migration is completed.

See [CHANGELOG.md](CHANGELOG.md) for the full history.

## Development and Building

### Technology Stack

| Area | Technology |
|---|---|
| Desktop UI | Flet / Flutter |
| Online speech | edge-tts |
| Local speech | Kokoro + sherpa-onnx sidecar |
| Audio playback | pygame |
| Windows integration | pywin32, pynput, pystray, pyperclip |
| Images and tray | Pillow |

### Project Structure

```text
Anki-TTS-Edge/
├── .github/              # CI and Dependabot
├── Anki-TTS-Flet/
│   ├── assets/           # Icons, translations, and local-engine manifest
│   ├── config/           # Constants and user settings
│   ├── core/             # TTS, playback, monitors, history, and local engine
│   ├── ui/               # Flet pages and controls
│   ├── utils/            # Shared utilities
│   ├── main.py           # Application entry point
│   └── requirements.txt  # Pinned direct dependencies
├── tests/                # Regression tests
├── tools/                # Runtime self-check tools
├── Anki-TTS-Edge.spec    # PyInstaller build configuration
├── ARCHITECTURE.md       # Architecture and maintenance constraints
└── CHANGELOG.md          # Release history
```

### Build the Windows Application

The project uses PyInstaller in `onedir` mode. Do not switch to `onefile`; it increases startup delay and antivirus scanning risk.

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe -y --clean Anki-TTS-Edge.spec
```

The output is written to `dist/Anki-TTS-Edge/`, with `Anki-TTS-Edge.exe` as the entry point. Distributions must keep the complete directory and the adjacent `LICENSE` and `NOTICE` files.

### Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv\Scripts\python.exe tools\flet_runtime_selfcheck.py
.\.venv\Scripts\python.exe -m compileall -q Anki-TTS-Flet scripts tools
```

More maintenance documentation:

- [ARCHITECTURE.md](ARCHITECTURE.md): Runtime flow, state boundaries, and safety constraints.
- [MAINTENANCE.md](MAINTENANCE.md): Python, dependency, and Flet upgrade policy.
- [CHANGELOG.md](CHANGELOG.md): Complete release history.

## License and Third-Party Services

Anki-TTS-Edge is distributed under [GPL-3.0-only](LICENSE). See [NOTICE](NOTICE) for third-party notices.

This software is not an official Microsoft product. Users of Microsoft Edge TTS or other third-party services must comply with applicable laws and service terms; those terms do not change this project's open-source license.

The software is provided “as is,” without warranties of any kind. Users are responsible for evaluating the risks of downloading, installing, and using it.

<div align="center">

Made with ❤️ for Language Learners

</div>
