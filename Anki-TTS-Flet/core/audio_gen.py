import os
import re
import asyncio
import json
import hashlib
import edge_tts
from config.constants import AUDIO_DIR
from utils.text import sanitize_text
from utils.i18n import i18n

from core.alignment import AlignmentEngine

async def generate_audio_with_timestamps_async(text, voice, rate, volume, pitch, output_path):
    """
    Async function to generate audio using edge_tts and capture word boundaries.
    Returns (output_path, timestamps_data) or (None, None) on error.
    """
    try:
        # boundary='WordBoundary' required since edge-tts 7.x changed default to SentenceBoundary
        comm = edge_tts.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch, boundary="WordBoundary")
        
        word_boundaries = []
        audio_chunks = []
        
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset and duration are in 100-nanosecond units
                # We store them raw or simplified? AlignmentEngine handles raw logic?
                # Let's keep consistency with original dict but no manual char mapping
                word_boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"],
                    "duration": chunk["duration"]
                })
        
        # Write audio file
        with open(output_path, "wb") as f:
            for chunk in audio_chunks:
                f.write(chunk)
        
        # Use AlignmentEngine to generate precise mappings
        engine = AlignmentEngine()
        alignment_data = engine.align(text, word_boundaries)
        
        # Create timestamps data
        timestamps_data = {
            "text": text,
            "sentences": alignment_data["sentences"],
            "words": alignment_data["words"]
        }
        
        # Save timestamps to JSON file
        timestamps_path = output_path.replace(".mp3", ".timestamps.json")
        with open(timestamps_path, "w", encoding="utf-8") as f:
            json.dump(timestamps_data, f, ensure_ascii=False, indent=2)
        
        print(i18n.get("debug_edge_tts_ok", output_path))
        print(f"DEBUG: Timestamps saved to {timestamps_path}")
        
        return output_path, timestamps_data
        
    except Exception as e:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass
        try:
            timestamps_path = output_path.replace(".mp3", ".timestamps.json")
            if os.path.exists(timestamps_path):
                os.remove(timestamps_path)
        except Exception:
            pass
        msg = str(e)
        if "No audio was received" in msg:
            msg += " (Hint: Does this voice support the text language?)"
        print(i18n.get("debug_edge_tts_fail", msg))
        # Let caller surface the actual error instead of a generic "internal error".
        raise RuntimeError(msg) from e


async def generate_audio_task(text, voice, rate, volume, pitch):
    """
    Pure async wrapper for Flet usage.
    Returns (path, error, timestamps_data).
    """
    text = sanitize_text(text)
    if not text:
        return None, i18n.get("debug_empty_text"), None

    cache_payload = json.dumps(
        {
            "text": text,
            "voice": voice,
            "rate": rate,
            "volume": volume,
            "pitch": pitch,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    cache_key = hashlib.sha1(cache_payload.encode("utf-8")).hexdigest()
    match = re.search(r", (.*Neural)\)$", voice)
    part = re.sub(r'\W+', '', match.group(1)) if match else "Unknown"
    fname = f"Anki-TTS-Edge_{part}_{cache_key[:16]}.mp3"
    out_path = os.path.join(AUDIO_DIR, fname)

    if os.path.exists(out_path):
        cached_timestamps = load_timestamps(out_path)
        if cached_timestamps:
            print(f"DEBUG: Audio cache hit -> {out_path}")
            return out_path, None, cached_timestamps
    
    print(i18n.get("debug_generating_audio", voice, rate, volume, pitch))
    print(i18n.get("debug_output_path", out_path))

    try:
        result, timestamps = await generate_audio_with_timestamps_async(
            text, voice, rate, volume, pitch, out_path
        )
        if result:
            return result, None, timestamps
        else:
            return None, i18n.get("debug_edge_tts_internal_error"), None
    except Exception as e:
        return None, str(e), None


def load_timestamps(audio_path):
    """
    Load timestamps data from JSON file associated with an audio file.
    Returns timestamps_data dict or None if not found.
    """
    timestamps_path = audio_path.replace(".mp3", ".timestamps.json")
    if os.path.exists(timestamps_path):
        try:
            with open(timestamps_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"DEBUG: Failed to load timestamps: {e}")
    return None
