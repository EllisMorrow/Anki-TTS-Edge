# Anki-TTS-Edge

**[中文文档](https://github.com/EllisMorrow/Anki-TTS-Edge/blob/master/README.md)**

<div align="center">

Anki-TTS-Edge is a free, high-quality voice generation tool powered by Microsoft Edge TTS. It **quickly generates audio from selected text**, supports dual-voice mode for generating audio with two different voices, and automatically copies the generated audio to clipboard for fast pasting into apps like Anki. It also serves as a **convenient reading tool for language learning and article reading**.
**Completely rebuilt with Flet (Flutter) in v2.0**, featuring a modern UI, smooth animations, and enhanced functionality.

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/EllisMorrow/Anki-TTS-Edge)](https://github.com/EllisMorrow/Anki-TTS-Edge/releases/latest) [![GitHub last commit](https://img.shields.io/github/last-commit/EllisMorrow/Anki-TTS-Edge)](https://github.com/EllisMorrow/Anki-TTS-Edge/commits/master) [![GitHub All Releases Downloads](https://img.shields.io/github/downloads/EllisMorrow/Anki-TTS-Edge/total?label=Downloads&color=brightgreen)](https://github.com/EllisMorrow/Anki-TTS-Edge/releases)

</div>

## 🔄 Latest Stabilization Update (v2.9.3)

- **Hardened offline-engine installation**: SHA-256 validation is strict; archive traversal, links, and device entries are rejected; failed downloads remove partial files.
- **Safer data persistence and cleanup**: Settings, history, and voice cache use atomic writes. History deletion cannot escape the managed audio directory, and deep cleanup now includes local-engine WAV files.
- **New anti-aliased icon**: Preserves the original blue/green/red circular identity with a 1024px master and nine Windows ICO sizes from 16px through 256px.
- **Release and maintenance improvements**: Completes GPL-3.0-only and third-party notices, includes licenses in packaged builds, pins direct dependencies, and adds Python 3.10/3.13 Windows CI plus Dependabot.
- Flet and flet-desktop intentionally remain on 0.28.3 until a dedicated UI and packaging migration is validated.

## ✨ Key Features

- **Modern UI**: Built with Flet (Flutter) for a sleek, responsive experience with dark/light theme support.
- **300+ Free Voices**: Access the full Microsoft Edge Neural TTS voice library across dozens of languages and regional accents.
- **Real-time Word Highlighting**: Words are highlighted in sync during playback, handling complex mappings (e.g. "1" -> "one") perfectly.
- **Click-to-Play**: Click any word or character during playback to instantly start from that exact position.
- **Smart Navigation**: "Previous/Next Sentence" controls for easy sentence-by-sentence review.
- **Dual Voice Mode**: Stable dual-slot voice configuration for quick switching between two voices (e.g., Male/Female, US/UK accents).
- **History Management**: Automatically saves generation history. Re-listen, delete, or clear records; deep cleanup reclaims orphaned files.
- **Smart Monitoring**:
  - **Copy to Generate**: Automatically generates audio from copied text and can autoplay based on settings.
  - **Selection Single/Dual Voice Mode**: (Windows) Use `GO / A / B` after text selection to choose how audio is generated.
- **Offline TTS Engine (Optional)**: install/validate/uninstall and switch to Local Kokoro from Settings (downloaded sidecar, keeps the main app small).
- **System Integration**:
  - **Tray Support**: Minimize to system tray to keep your workspace clean.
  - **Pin to Top**: Keep the window always on top for studying.
  - **Internationalization**: Full English and Chinese UI with live switching.
  - **Centralized Data**: All user data stored in `%APPDATA%/Anki-TTS-Edge/` for clean organization.

## 📸 Screenshots

<div align="center">
<img  alt="image" src="https://github.com/user-attachments/assets/c9fade87-7a3f-4ccf-858c-07c2acb6f2e2" />

</div>

> *Note: New Flet interface, clean and intuitive.*

## 🚀 Installation & Running

### Requirements
- Python 3.10+
- Windows (Recommended for full feature support like Selection Monitor)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/EllisMorrow/Anki-TTS-Edge.git
   cd Anki-TTS-Edge
   ```

2. **Install Dependencies**
   ```bash
   pip install -r Anki-TTS-Flet/requirements.txt
   ```
   *Note: If `requirements.txt` is missing, manually install:*
   ```bash
   pip install flet==0.28.3 flet-desktop==0.28.3 edge-tts==7.2.8 pygame==2.6.1 pyperclip==1.11.0 pynput==1.8.2 pystray==0.19.5 Pillow==12.3.0 pywin32==312
   ```

3. **Run Application**
   ```bash
   python Anki-TTS-Flet/main.py
   ```

## 👨‍💻 Developer Guide

Welcome developers to contribute and customize Anki-TTS-Edge! Below are the core architecture details and guidelines for the project.

### Technology Stack
* **UI Framework**: Flet (Python UI framework based on Flutter), providing responsive design and fluid animations.
* **Core TTS Engine**: `edge-tts` (Unofficial implementation of Microsoft Edge neural voice API).
* **Audio & Media**: `pygame` (Provides stable, low-latency multi-threaded audio playback capabilities).
* **System Integration**: `pyperclip` (Clipboard monitoring), `pystray` / `pillow` (System tray integration).
* **Asynchronous Concurrency**: Heavy usage of Python's `asyncio` for non-blocking I/O operations, ensuring the UI thread remains smooth during network requests or playback.

### Core Technical Highlights
1. **Subtitle-Level Alignment (Text-to-Speech Alignment)**
   Leverages `edge-tts` word boundaries and timestamps to dynamically update Flet's `TextSpan` and `TextStyle` within the audio playback callback, achieving "Karaoke-style" exact word synchronization.
2. **Global Input & Clipboard Monitor**
   A dedicated background thread continuously polls the system clipboard (or detects selected text). Upon detecting a change, it immediately brings the application window to the forefront (Bring to Front), eliminating cumbersome manual copy-paste steps during flashcard creation.
3. **Audio State & Garbage Collection**
   Implemented an aggressive cleanup mechanism in the history management module. It uses hashing and path tracking for audio and metadata (`.json`), and automatically iterates through local file lists during deletion to confidently discard "orphaned" files.
4. **Componentization & State Management**
   The UI is divided into independent routed views (Home, History, Settings) that communicate with low coupling via a global state manager or dependency injection.

### 📂 Project Structure

```text
Anki-TTS-Edge/
├── ARCHITECTURE.md      # Architecture decisions and maintenance memory
├── Anki-TTS-Flet/       # Main compiled source code
│   ├── assets/          # Static resources like icons and localization files
│   ├── config/          # Default configurations and settings I/O
│   ├── core/            # Business logic brain (TTS engine, Alignment, Monitors, History IO)
│   ├── ui/              # Flet UI Views (Modular pages and custom UI components)
│   ├── utils/           # General helper functions (File ops, text formatting, etc.)
│   └── main.py          # Application entry point and initialization
├── .gitignore           # Git ignore rules
└── README.md            # Documentation
```

### 🔨 Building an Executable (EXE)

To bundle the application into a standalone Windows executable, we use PyInstaller in **folder (onedir) mode**:

> ⚠️ **Important**: Do NOT use `--onefile` mode. Single-file mode causes extremely slow startup on Windows (the entire application must be extracted to a temp directory on every launch, and frequently triggers antivirus scans).

```bash
# Ensure PyInstaller is installed in your virtual environment
pip install pyinstaller

# Run the build command from the project root (folder mode). Prefer using the repo .spec for repeatable builds.
.\.venv\Scripts\pyinstaller.exe -y --clean Anki-TTS-Edge.spec
```

Upon successful build, the `dist/Anki-TTS-Edge/` directory contains the complete distributable application, with `Anki-TTS-Edge.exe` as the entry point.

## 🛠️ Usage Guide

1. **Select Voice**: Use the dropdown menus to filter by Language and Region.
2. **Generate**: Type or paste text, then click the **Blue Dot** to generate audio.
   - **Left Dot**: Uses "Language (Left)" settings.
   - **Right Dot**: Uses "Language (Right)" settings.
3. **Copy File**: After generation (Green -> Red dot), click the Red dot or use **Ctrl+C** to copy the audio file path (for pasting into Anki).
4. **History**: Switch to the **History** tab to view and manage past generations.
5. **Settings**: Customize theme (Dark/Light), behavior (Autoplay, Tray), and more in the **Settings** tab.
   - For offline mode: switch the “TTS Engine” to Offline and click “Download & Install”. After install, click “Re-validate” to confirm.

---
<div align="center">
Made with ❤️ for Language Learners
</div>

---

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md)

---

## ⚠️ Disclaimer

Anki-TTS-Edge is open-source software distributed under the GPL-3.0-only license.

1.  **Third-party services**: This software is not an official Microsoft product. When using Microsoft Edge TTS or any other third-party service, users must comply with applicable laws and the relevant service terms; those terms do not change this project's GPL-3.0-only software license.
2.  **No Liability**:
    *   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    *   **IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**
    *   Users assume all risks associated with downloading, installing, and using this software.
3.  **Compliance**: Users must comply with local laws and regulations and Microsoft's relevant terms of service when using this software. Any legal liability arising from violation of laws or terms of service shall be borne solely by the user.

This section describes third-party service use and liability boundaries only. The GPL-3.0-only in [LICENSE](LICENSE) governs rights to copy, modify, and distribute this software.
