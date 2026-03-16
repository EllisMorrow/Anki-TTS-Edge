# 本地 Kokoro 边车接入设计文档

更新时间：2026-03-16

## 背景与需求（可脱离聊天窗理解）

背景：

- 在线微软 Edge TTS 在部分网络环境下响应很慢，影响“复制后生成/划词生成”的即时性。

需求：

- 以“边车模式”接入一个离线语音引擎，能高速响应、音质自然、尽量低幻觉、多语言可读。
- 主程序本体保持足够小，不把 ONNX 推理/模型权重强行塞进 EXE。
- 设置页提供“一键切换”在线/本地。
- 提供“自动下载 + 手动下载”两条安装路径，并且每条路径都支持“官方源 + 可靠镜像源”。
- 下载必须防呆：大文件下载后必须做哈希校验（优先 SHA256）。

V1 务实约束：

- 本地模式先不追求逐词高亮/点击跳播；但接口必须预留 timestamps 字段，以便未来无痛补齐。
- 本地模式先优先保证 `中文 + 英文`（其他语言可自动回退在线）。

## 执行计划（Checklist + 状态）

状态说明：

- `[ ]` 未开始
- `[..]` 进行中
- `[x]` 已完成

### Phase 0：方案固化（文档）

- [x] 选定默认路线：`sherpa-onnx` 预编译 Windows x64 可执行文件 + Kokoro 模型包
- [x] 明确 V1 降级边界（timestamps 空、无逐词高亮/跳播）
- [x] 目录结构/设置项/下载回退/校验策略写入文档

### Phase 1：Provider 抽象（不改 UI，保证在线链路不回归）

- [x] 新增 `TTSProvider` 抽象接口
- [x] 新增统一返回结构：预留 `timestamps`（本地先返回空）
- [x] 新增 Provider Registry（根据设置选择引擎）
- [x] 先把在线 Edge TTS 适配成 Provider（行为保持不变）
- [x] 自检：`compileall` + `scripts/flet_selfcheck.py`

### Phase 2：LocalEngineManager（下载/校验/安装/卸载/健康检查）

- [x] 引擎目录固定到 `%APPDATA%\\Anki-TTS-Edge\\providers\\kokoro\\`
- [x] 引擎清单 `manifest.json`（官方源 + 镜像源）
- [x] 下载实现（断点不做也行，但必须可重试）
- [x] 校验实现（SHA256）：从 `checksum.txt` 获取预期哈希并验证
- [x] 解压实现：`.tar.bz2` 解到 `model/`
- [x] 健康检查：短文本生成一次音频（WAV），确认可运行
- [x] 输出“手动下载指令”结构（含目标目录、命令、链接、校验说明）
- [x] 实机验收：跑一次真实下载 + 健康检查（会下载约 150MB+）

### Phase 3：LocalKokoroProvider（子进程调用，timestamps 为空）

- [x] 调 `sherpa-onnx` 本地 CLI 生成 WAV（不引入 ffmpeg）
- [x] 生成结果进入现有：历史/播放/复制到剪贴板/缓存（音频扩展名允许 wav）
- [x] 本地不可用时按设置自动回退在线（并给用户明确提示）

### Phase 4：设置页接线（UI 一键切换 + 下载按钮）

- [x] 设置页新增“语音引擎”区块：在线/本地一键切换
- [x] 自动下载按钮（后台任务执行，UI 显示状态）
- [x] 手动下载按钮（弹窗展示命令 + 官方/镜像链接 + 目标目录）
- [x] 状态显示：未安装/安装中/可用/失败（含 last_error）

### Phase 5：发布与维护

- [ ] 构建验证：PyInstaller onedir + 冒烟启动
- [ ] 文档补充：使用说明（离线模式能力边界、支持语言、文件格式）
- [ ] 发布：tag + GitHub Release（离线引擎本体不随主包发布）

## 当前进度

- Phase 0：已完成（仅文档）
- Phase 1：已完成（Edge Provider 已接入，行为不变）
- Phase 2：已完成（真实下载 + SHA256 校验 + 健康检查通过）
- Phase 3：已完成（本地 Provider 可生成 WAV，timestamps 预留为空）
- Phase 4：已完成（设置页一键切换 + 下载/校验/卸载/手动下载）
- Phase 5：未开始

## 实施记录（时间线）

- 2026-03-15：完成本设计文档初版并定默认路线（`sherpa-onnx + Kokoro`）
- 2026-03-16：开始按本计划进入 Phase 1（Provider 抽象）
- 2026-03-16：完成 Phase 1（`TTSProvider/TTSManager` 与 `EdgeTTSProvider` 接线，自检通过）
- 2026-03-16：实现 Phase 2（`LocalEngineManager` + manifest + SHA256 校验 + 安装/卸载/健康检查）
- 2026-03-16：发现模型文件名为 `model.int8.onnx`（非 `model.onnx`），补齐自动识别逻辑
- 2026-03-16：发现单文件运行时 `sherpa-onnx-non-streaming-tts-x64-*.exe` 在部分 Windows 环境下会卡死/不可用，改为下载 `sherpa-onnx-*-win-x64-*-MT-Release.tar.bz2`（含可用的 `sherpa-onnx-offline-tts.exe`），并通过 manifest `version` 自动升级旧 manifest

## 0. 先说结论

这不是“1 小时内的小工程”。

如果只写方案，1 小时内可以完成。
如果要把它真正做成：

- 可一键切换
- 可下载
- 可校验
- 可回退
- 不污染主程序运行环境
- 不破坏现有在线 Edge TTS 链路

那它是一个中等规模改造，不该按“小活”预期。

## 1. V1 目标

V1 不追求“离线模式完全复刻在线模式”，只追求：

- 本地模式能稳定发声
- 主程序保持干净
- 模型和运行时可选下载
- 下载失败时仍有手动安装路径
- 本地模式与在线模式可一键切换
- 现有主逻辑尽量少改

V1 明确接受以下降级：

- 本地模式先不支持逐词高亮
- 本地模式先不支持点击单词跳播
- 本地模式返回的 `timestamps` 固定为空
- 本地模式先只承诺 `中文 + 英文`
- 非 `中文/英文` 文本仍建议自动回退到在线 Edge TTS

## 2. 默认技术路线

### 2.1 最终选择

默认下载项选择：

- `sherpa-onnx` 预编译 Windows x64 可执行文件
- 配套 `Kokoro v1.x` 预训练包

默认执行方式选择：

- `V1` 采用“直接子进程调用”模式
- 不做常驻本地 HTTP 服务
- 但接口层预留未来切换到本地 HTTP 的能力

### 2.2 为什么默认不用 `kokoro-onnx` 当 V1 主方案

`kokoro-onnx` 很优秀，但它当前更像“成熟 Python Runtime + 模型文件”，不是“最省事的 Windows 桌面边车可执行方案”。

我查到的现实情况是：

- `thewh1teagle/kokoro-onnx` 明确提供 `ONNX` 运行时方案，支持多语言、多声音，模型体积约 `300MB`，量化版约 `80MB`。[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases)
- 但它公开主路径仍是 `pip/uv + Python` 集成，不是现成的 Windows 单文件/单目录边车服务方案。[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)
- 它还依赖 `misaki g2p` 等文本前端链路，Windows 桌面端打包时更容易把问题带进主产品。

相对地：

- `sherpa-onnx` 官方仓库明确支持 `Windows x64`，并长期发布预编译二进制与运行时资产。[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- `sherpa-onnx` 的 Kokoro 文档直接给出了 “用编译好的 C++ 可执行文件生成语音” 的用法。[sherpa Kokoro docs](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html)
- 它的公开定位就是本地离线推理框架，天然更适合桌面软件边车模式。[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)

### 2.3 为什么默认选 `sherpa-onnx + Kokoro`

这是当前对 Windows/Flet 桌面端最务实的方案：

1. 现成可执行程序路线更稳  
   不把 Python 科学计算依赖带进主程序。

2. 平台支持明确  
   `sherpa-onnx` 官方仓库明确写了支持 `Windows x64`。[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)

3. 官方文档已有 Kokoro 集成指引  
   包括模型下载和离线 TTS 命令样例。[sherpa Kokoro docs](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html)

4. V1 语言边界清晰  
   官方 Kokoro 文档对 `v1_0` 直接写明：这是多语言模型，但 `sherpa-onnx` 当前只加了 `English + Chinese` 支持。[sherpa Kokoro docs](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html)

5. 许可更干净  
   `sherpa-onnx` 是 `Apache-2.0`；`kokoro-onnx` Runtime 是 `MIT`、模型是 `Apache-2.0`，两边都可商用友好，但 `sherpa-onnx` 更接近“可以直接下可执行文件就用”的发布模式。[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx)

## 3. 真实能力边界

### 3.1 V1 保证

- `中文 + 英文` 可离线生成
- 音频自然度较好
- 非自回归，基本不会出现自说自话式幻觉
- 本地模式生成结果可进入现有历史记录、播放、缓存、复制 MP3 到剪贴板链路

### 3.2 V1 不保证

- 不保证逐词时间戳
- 不保证词级高亮
- 不保证点击单词跳播
- 不保证所有多语言文本都本地可读

### 3.3 产品策略

默认策略：

- 如果当前引擎为 `local_kokoro`
- 且文本语言命中 `zh/en`
- 则走本地
- 否则自动回退到 `edge_online`

设置中提供一个开关：

- `本地模式仅支持中文/英文，其他语言自动回退在线`

默认开启。

## 4. 目录结构

所有本地引擎资产统一放在：

`%APPDATA%\\Anki-TTS-Edge\\providers\\kokoro\\`

建议目录：

```text
%APPDATA%\Anki-TTS-Edge\
├─ providers\
│  └─ kokoro\
│     ├─ manifest.json
│     ├─ install_state.json
│     ├─ downloads\
│     │  ├─ sherpa-onnx-v1.12.29-win-x64.zip
│     │  ├─ kokoro-int8-multi-lang-v1_1.tar.bz2
│     │  └─ checksums.json
│     ├─ runtime\
│     │  ├─ sherpa-onnx-offline-tts.exe
│     │  ├─ onnxruntime.dll
│     │  ├─ onnxruntime_providers_shared.dll
│     │  └─ ...其余运行时文件
│     ├─ model\
│     │  ├─ model.onnx
│     │  ├─ voices.bin
│     │  ├─ tokens.txt
│     │  ├─ lexicon-us-en.txt
│     │  ├─ lexicon-zh.txt
│     │  ├─ espeak-ng-data\
│     │  └─ dict\
│     ├─ cache\
│     │  └─ *.wav
│     └─ logs\
│        └─ kokoro_runner.log
├─ audio\
├─ history.json
├─ voice_settings.json
└─ ...
```

## 5. 配置与状态

在现有设置里新增：

```json
{
  "tts_engine": "edge_online",
  "local_engine_auto_fallback": true,
  "local_engine_download_source": "official",
  "local_engine_preferred_variant": "kokoro_int8_v1_1",
  "local_engine_install_dir": "",
  "local_engine_ready": false,
  "local_engine_last_healthcheck": 0,
  "local_engine_last_error": ""
}
```

说明：

- `tts_engine`
  - `edge_online`
  - `local_kokoro`
- `local_engine_auto_fallback`
  - 本地不支持或不可用时自动回退在线
- `local_engine_download_source`
  - `official`
  - `mirror`
- `local_engine_preferred_variant`
  - 默认先给量化版
- `local_engine_install_dir`
  - 为空时使用 `%APPDATA%` 默认目录

## 6. 下载清单设计

### 6.1 manifest.json

本地引擎不把下载地址硬编码在 Python 代码里，而是由 `manifest.json` 描述。

示例：

```json
{
  "provider": "local_kokoro",
  "version": "1.0",
  "default_variant": "kokoro_int8_v1_1",
  "variants": [
    {
      "id": "kokoro_int8_v1_1",
      "label": "Kokoro v1.1 INT8 (Recommended)",
      "languages": ["zh", "en"],
      "size_mb": 150,
      "runtime": {
        "archive_name": "sherpa-onnx-v1.12.29-win-x64.zip",
        "entry_exe": "runtime/sherpa-onnx-offline-tts.exe",
        "sha256": "..."
      },
      "model": {
        "archive_name": "kokoro-int8-multi-lang-v1_1.tar.bz2",
        "sha256": "..."
      },
      "sources": {
        "official": [
          "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.29/sherpa-onnx-v1.12.29-win-x64.zip",
          "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-int8-multi-lang-v1_1.tar.bz2"
        ],
        "mirror": [
          "https://your-mirror.example.com/anki-tts-edge/kokoro/sherpa-onnx-v1.12.29-win-x64.zip",
          "https://your-mirror.example.com/anki-tts-edge/kokoro/kokoro-int8-multi-lang-v1_1.tar.bz2"
        ]
      }
    }
  ]
}
```

### 6.2 为什么必须做 manifest

- 下载源和版本可以后改，不需要改代码
- 方便以后追加 `v1.1 full`、`CPU faster`、`更高音质` 变体
- 手动下载时可以直接从 manifest 生成终端命令

## 7. 下载与回退流程

### 7.1 自动下载流程

`LocalEngineManager.install_default()`：

1. 读取 `manifest.json`
2. 选择默认 variant
3. 检查本地是否已安装且哈希通过
4. 若未安装：
   - 下载 runtime 压缩包
   - 校验 SHA256
   - 解压到 `runtime/`
   - 下载 model 压缩包
   - 校验 SHA256
   - 解压到 `model/`
5. 写入 `install_state.json`
6. 运行一次健康检查

### 7.2 自动下载失败后的回退

顺序固定：

1. 官方源自动下载
2. 镜像源自动下载
3. 给用户展示手动下载信息

### 7.3 手动下载模式

设置页点击“手动下载”后，展示：

- 官方源地址
- 镜像源地址
- PowerShell 下载命令
- 解压后的目标目录
- 校验命令

示例文案：

```powershell
cd "$env:APPDATA\Anki-TTS-Edge\providers\kokoro\downloads"

Invoke-WebRequest -Uri "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.12.29/sherpa-onnx-v1.12.29-win-x64.zip" -OutFile "sherpa-onnx-v1.12.29-win-x64.zip"
Invoke-WebRequest -Uri "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-int8-multi-lang-v1_1.tar.bz2" -OutFile "kokoro-int8-multi-lang-v1_1.tar.bz2"
```

### 7.4 下载防呆：必须做哈希校验

要求：

- 优先 `SHA256`
- 不建议只做 `MD5`
- 校验失败时：
  - 删除损坏文件
  - 明确提示“下载文件校验失败，请重试或切换下载源”

建议代码接口：

```python
def compute_sha256(path: str) -> str: ...
def verify_file_sha256(path: str, expected: str) -> bool: ...
```

## 8. 核心抽象接口

### 8.1 统一返回结构

即便本地模式没有时间戳，也必须预留字段。

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimestampsPayload:
    text: str = ""
    words: list[dict[str, Any]] = field(default_factory=list)
    sentences: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""


@dataclass
class SynthesisRequest:
    text: str
    voice: str
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"
    output_path: str = ""
    language_hint: str = ""
    engine: str = "edge_online"


@dataclass
class SynthesisResult:
    ok: bool
    engine: str
    audio_path: str = ""
    error: str = ""
    timestamps: TimestampsPayload | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### 8.2 Provider 抽象

```python
from abc import ABC, abstractmethod


class TTSProvider(ABC):
    provider_id: str

    @abstractmethod
    def is_ready(self) -> bool:
        ...

    @abstractmethod
    def supports_language(self, language_hint: str, text: str) -> bool:
        ...

    @abstractmethod
    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        ...

    @abstractmethod
    def list_voices(self) -> list[dict]:
        ...
```

### 8.3 V1 的两个 Provider

```python
class EdgeTTSProvider(TTSProvider):
    provider_id = "edge_online"


class LocalKokoroProvider(TTSProvider):
    provider_id = "local_kokoro"
```

### 8.4 关键要求

无论哪个 Provider，主调用方都只收 `SynthesisResult`。

这意味着：

- 未来本地有时间戳了，只需要本地 Provider 开始填 `timestamps`
- 主逻辑无需改接口

## 9. LocalEngineManager 设计

### 9.1 职责

`LocalEngineManager` 只负责本地引擎生命周期，不负责业务 UI。

职责包括：

- 查询安装状态
- 自动下载
- 手动安装校验
- 健康检查
- 返回可执行路径与模型路径
- 卸载本地引擎

### 9.2 建议接口

```python
class LocalEngineManager:
    def get_status(self) -> dict: ...
    def is_installed(self) -> bool: ...
    def install_default(self) -> dict: ...
    def validate_installation(self) -> dict: ...
    def get_runtime_paths(self) -> dict: ...
    def uninstall(self) -> dict: ...
    def healthcheck(self) -> dict: ...
    def build_manual_download_instructions(self) -> dict: ...
```

### 9.3 健康检查

V1 不用 HTTP。

健康检查只做：

- `exe` 是否存在
- 关键模型文件是否存在
- `SHA256` 是否匹配
- 用一段短文本试生成一次到临时目录

若成功：

- `local_engine_ready = true`

否则：

- 记录 `last_error`
- 设置页显示“本地引擎不可用，已自动回退在线”

## 10. V1 执行模型

### 10.1 不是 HTTP，直接 CLI

V1 直接通过 `subprocess` 调 `sherpa-onnx-offline-tts.exe`。

这是最小改造，也是最稳的方案。

示意：

```python
cmd = [
    str(exe_path),
    f"--kokoro-model={model_dir / 'model.onnx'}",
    f"--kokoro-voices={model_dir / 'voices.bin'}",
    f"--kokoro-tokens={model_dir / 'tokens.txt'}",
    f"--kokoro-data-dir={model_dir / 'espeak-ng-data'}",
    f"--kokoro-lexicon={model_dir / 'lexicon-us-en.txt'},{model_dir / 'lexicon-zh.txt'}",
    "--num-threads=2",
    f"--sid={speaker_id}",
    f"--output-filename={output_path}",
    text,
]
```

### 10.2 为什么不用 HTTP

因为 V1 目标不是“平台化”，而是“先稳定可用”。

HTTP 会额外引入：

- 本地端口占用
- 服务启动管理
- 健康探针
- 请求超时与 JSON 协议
- 后台驻留生命周期

这些都不是 V1 必需品。

### 10.3 但要给 HTTP 留口子

`LocalKokoroProvider` 内部增加 `transport` 概念：

```python
class LocalKokoroProvider(TTSProvider):
    transport: Literal["process", "http"] = "process"
```

这样以后如果真要切到常驻 HTTP：

- `synthesize()` 内部改 transport
- 主逻辑不用改

## 11. 语音映射

### 11.1 V1 不尝试复刻 Edge voice name

本地模式声音和 Edge 声音不是同一套。

所以不做“同名映射”，而是单独维护：

- 在线声音选择
- 本地声音选择

设置项新增：

```json
{
  "local_voice_left": "zf_xiaoxiao",
  "local_voice_right": "am_michael"
}
```

### 11.2 为什么这样更稳

因为：

- Edge 声音列表是云端动态的
- Kokoro 声音列表是本地固定的
- 强做自动映射只会制造更多错误期待

## 12. 与现有代码的对接点

### 12.1 新增文件

建议新增：

```text
Anki-TTS-Flet/
├─ core/
│  ├─ tts_provider.py
│  ├─ tts_edge_provider.py
│  ├─ tts_local_kokoro_provider.py
│  ├─ local_engine_manager.py
│  ├─ download_manager.py
│  └─ checksums.py
```

### 12.2 修改点

需要修改：

- `core/audio_gen.py`
  - 从“只认 Edge”改为“调用 Provider”
- `config/settings.py`
  - 增加本地引擎设置项
- `ui/settings_view.py`
  - 增加引擎切换、下载、状态展示
- `main.py`
  - 初始化 provider registry
  - 切换当前引擎
  - 不支持语言时自动回退

### 12.3 最小改法

当前 `generate_audio_task()` 不要继续直接调 `edge-tts`。

改成：

```python
provider = provider_registry.get_current_provider()
result = await provider.synthesize(request)
```

然后保留现有：

- 历史记录写入
- 自动播放
- MP3 剪贴板
- 音频缓存

## 13. 设置页设计

建议新增一组：

```text
离线引擎
├─ 语音引擎：在线 Edge / 本地 Kokoro
├─ 本地引擎状态：未安装 / 已安装 / 校验失败 / 可用
├─ 自动下载
├─ 手动下载
├─ 下载源：官方源 / 镜像源
├─ 本地模式语言策略：仅中文英文 / 不支持则回退在线
├─ 本地声音 1
└─ 本地声音 2
```

### 13.1 手动下载按钮点击后展示

弹窗里要给：

- 官方源地址
- 镜像源地址
- PowerShell 命令
- 目标目录
- “安装完成后点重新校验”按钮

## 14. 失败回退策略

### 14.1 生成前

如果：

- 本地引擎未安装
- 哈希校验失败
- 健康检查失败
- 文本不是 `zh/en`

则：

- 若 `local_engine_auto_fallback = true`
  - 自动回退 `edge_online`
- 否则：
  - 直接报错并提示安装/切换

### 14.2 生成中

如果本地进程失败：

- 记录 `stderr`
- 设置 `last_error`
- 本次请求自动回退在线
- 状态栏提示：
  - “本地引擎失败，已自动切回在线模式”

### 14.3 生成后

无论本地还是在线，主逻辑统一写入：

- `history`
- `audio cache`
- `playback state`

## 15. 时间戳预留策略

V1 本地模式：

```python
SynthesisResult(
    ok=True,
    engine="local_kokoro",
    audio_path="...",
    timestamps=TimestampsPayload(
        text=request.text,
        words=[],
        sentences=[],
        source="local_kokoro:none"
    )
)
```

这样现有主逻辑可以统一判断：

- `timestamps.words` 为空 -> 不显示逐词高亮
- 不需要特殊分支污染主控制器

## 16. 发布与下载源建议

### 16.1 官方源

优先官方源：

- `sherpa-onnx` GitHub Releases
- `k2-fsa` 发布的 Kokoro TTS 模型包

参考：

- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)
- [sherpa Kokoro docs](https://k2-fsa.github.io/sherpa/onnx/tts/pretrained_models/kokoro.html)

### 16.2 镜像源

不要依赖随机第三方镜像。

建议你自己的镜像源放在：

- 你自己的 GitHub Releases
- 或对象存储

原因：

- 地址稳定
- 可控
- 校验值由你自己维护

## 17. V1 开发拆分

### Phase 1

- 抽象 `TTSProvider`
- 保持在线 Edge 可用

### Phase 2

- 加入 `LocalEngineManager`
- 做安装状态、校验、卸载

### Phase 3

- 接 `sherpa-onnx` 本地 CLI
- 跑通本地生成

### Phase 4

- 设置页引擎切换
- 下载源与手动下载弹窗

### Phase 5

- 自动回退
- 历史/缓存/播放整体验证

## 18. 最终决策

本项目 V1 本地离线语音方案，最终拍板如下：

- 主方案：`sherpa-onnx` 预编译 Windows x64 可执行文件
- 模型：`Kokoro v1.x` 量化版本优先
- 传输：`V1 = direct subprocess`，不是常驻 HTTP
- 语言承诺：`中文 + 英文`
- 非支持语言策略：自动回退在线 Edge
- 时间戳策略：接口预留，V1 固定返回空
- 下载策略：官方源 -> 镜像源 -> 手动下载
- 文件完整性：强制 `SHA256`

这条路线的优点不是“最花哨”，而是：

- 最能落地
- 最不容易把主程序拖脏
- 最适合当前项目的 Windows/Flet 桌面发布现实
