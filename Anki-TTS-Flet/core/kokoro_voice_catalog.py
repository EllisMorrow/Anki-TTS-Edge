from __future__ import annotations

from typing import Any

KOKORO_MULTI_LANG_V1_1_DOC_URL = (
    "https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html"
)


# Speaker ID mapping from sherpa-onnx sample page:
# - af: American female (sid 0-1)
# - bf: British female (sid 2)
# - zf: Chinese female (sid 3-57)
# - zm: Chinese male (sid 58-102)
_V1_1_EN_FEMALE = [
    "af_maple",  # sid 0
    "af_sol",  # sid 1
    "bf_vale",  # sid 2
]

_V1_1_ZH_FEMALE = [
    "zf_001",
    "zf_002",
    "zf_003",
    "zf_004",
    "zf_005",
    "zf_006",
    "zf_007",
    "zf_008",
    "zf_017",
    "zf_018",
    "zf_019",
    "zf_021",
    "zf_022",
    "zf_023",
    "zf_024",
    "zf_026",
    "zf_027",
    "zf_028",
    "zf_032",
    "zf_036",
    "zf_038",
    "zf_039",
    "zf_040",
    "zf_042",
    "zf_043",
    "zf_044",
    "zf_046",
    "zf_047",
    "zf_048",
    "zf_049",
    "zf_051",
    "zf_059",
    "zf_060",
    "zf_067",
    "zf_070",
    "zf_071",
    "zf_072",
    "zf_073",
    "zf_074",
    "zf_075",
    "zf_076",
    "zf_077",
    "zf_078",
    "zf_079",
    "zf_083",
    "zf_084",
    "zf_085",
    "zf_086",
    "zf_087",
    "zf_088",
    "zf_090",
    "zf_092",
    "zf_093",
    "zf_094",
    "zf_099",
]

_V1_1_ZH_MALE = [
    "zm_009",
    "zm_010",
    "zm_011",
    "zm_012",
    "zm_013",
    "zm_014",
    "zm_015",
    "zm_016",
    "zm_020",
    "zm_025",
    "zm_029",
    "zm_030",
    "zm_031",
    "zm_033",
    "zm_034",
    "zm_035",
    "zm_037",
    "zm_041",
    "zm_045",
    "zm_050",
    "zm_052",
    "zm_053",
    "zm_054",
    "zm_055",
    "zm_056",
    "zm_057",
    "zm_058",
    "zm_061",
    "zm_062",
    "zm_063",
    "zm_064",
    "zm_065",
    "zm_066",
    "zm_068",
    "zm_069",
    "zm_080",
    "zm_081",
    "zm_082",
    "zm_089",
    "zm_091",
    "zm_095",
    "zm_096",
    "zm_097",
    "zm_098",
    "zm_100",
]


def kokoro_v1_1_sid_to_name(sid: int) -> str | None:
    try:
        sid = int(sid)
    except Exception:
        return None

    if 0 <= sid <= 2:
        return _V1_1_EN_FEMALE[sid]
    if 3 <= sid <= 57:
        idx = sid - 3
        if 0 <= idx < len(_V1_1_ZH_FEMALE):
            return _V1_1_ZH_FEMALE[idx]
        return None
    if 58 <= sid <= 102:
        idx = sid - 58
        if 0 <= idx < len(_V1_1_ZH_MALE):
            return _V1_1_ZH_MALE[idx]
        return None
    return None


def kokoro_v1_1_name_to_sid(name: str) -> int | None:
    n = str(name or "").strip()
    if not n:
        return None
    try:
        return _V1_1_EN_FEMALE.index(n)
    except ValueError:
        pass
    try:
        return 3 + _V1_1_ZH_FEMALE.index(n)
    except ValueError:
        pass
    try:
        return 58 + _V1_1_ZH_MALE.index(n)
    except ValueError:
        pass
    return None


def build_kokoro_v1_1_voice_catalog(ui_lang: str = "zh") -> list[dict[str, Any]]:
    """
    Return a list compatible with HomeView.populate_voices():
      - name: speaker name (e.g. zf_001)
      - region: group label (e.g. 中文女声)
      - lang: hint for future filtering
      - sid: numeric speaker id for LocalKokoroProvider
      - engine: 'local_kokoro'
    """

    is_en = str(ui_lang or "").lower().startswith("en")
    groups = {
        "us_female": "US English (Female)" if is_en else "美式女声",
        "uk_female": "UK English (Female)" if is_en else "英式女声",
        "zh_female": "Chinese (Female)" if is_en else "中文女声",
        "zh_male": "Chinese (Male)" if is_en else "中文男声",
    }

    out: list[dict[str, Any]] = []

    # English female (US/UK)
    for sid, speaker in enumerate(_V1_1_EN_FEMALE):
        group = "us_female" if speaker.startswith("af_") else "uk_female"
        out.append(
            {
                "engine": "local_kokoro",
                "sid": sid,
                "name": speaker,
                "lang": "en",
                "region": groups[group],
                "display_name": f"{speaker} (sid={sid})",
            }
        )

    # Chinese female
    for i, speaker in enumerate(_V1_1_ZH_FEMALE):
        sid = 3 + i
        out.append(
            {
                "engine": "local_kokoro",
                "sid": sid,
                "name": speaker,
                "lang": "zh",
                "region": groups["zh_female"],
                "display_name": f"{speaker} (sid={sid})",
            }
        )

    # Chinese male
    for i, speaker in enumerate(_V1_1_ZH_MALE):
        sid = 58 + i
        out.append(
            {
                "engine": "local_kokoro",
                "sid": sid,
                "name": speaker,
                "lang": "zh",
                "region": groups["zh_male"],
                "display_name": f"{speaker} (sid={sid})",
            }
        )

    return out

