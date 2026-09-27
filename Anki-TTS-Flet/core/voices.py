import re
import asyncio
from edge_tts import VoicesManager
from utils.i18n import i18n
from core.voice_db import save_voice_cache, load_voice_cache

def get_cached_voices():
    """Load voices from local cache (instant)"""
    cache = load_voice_cache()
    if cache and isinstance(cache, list) and len(cache) > 0:
        print(f"DEBUG: Loaded {len(cache)} voices from cache")
        return cache
    return None

async def fetch_voices_from_network():
    """Fetch a complete, valid voice catalog and update the cache."""
    try:
        voices = await VoicesManager.create()
        raw_list = voices.find()

        if not isinstance(raw_list, list) or not raw_list:
            return []
        pattern = re.compile(
            r"^Microsoft Server Speech Text to Speech Voice \(([a-z]{2,3})-"
            r"((?:[A-Z][a-z]{3}-)?(?:[A-Z]{2}|[0-9]{3})(?:-[A-Za-z]+)?), (.*Neural)\)$"
        )
        processed_list = []

        for v in raw_list:
            if not isinstance(v, dict) or not isinstance(v.get("Name"), str):
                return []
            match = pattern.fullmatch(v["Name"])
            if not match:
                # A changed API format may have yielded a partial visible list.
                # Keep the last good cache and favorites until it can be checked.
                return []
            lang, region, name_part = match.groups()
            processed_list.append({
                "name": v["Name"],
                "lang": lang,
                "region": region,
                "display_name": name_part
            })

        if len({voice["name"] for voice in processed_list}) != len(processed_list):
            return []
        
        processed_list.sort(key=lambda x: (x['lang'], x['region'], x['name']))
        
        # Save to cache for next startup
        save_voice_cache(processed_list)
        print(i18n.get("debug_voices_loaded", len(processed_list)))
        return processed_list
        
    except Exception as e:
        print(i18n.get("debug_voices_load_failed", e))
        return []

async def get_available_voices_async():
    """
    Returns cached voices immediately if available.
    If no cache, fetches from network.
    """
    cached = get_cached_voices()
    if cached:
        return cached
    
    # No cache, must fetch from network
    return await fetch_voices_from_network()

def get_display_voice_name(name, voice_map=None):
    """
    Helper to get a display friendly name for a voice.
    If voice_map is provided, it tries to find the reverse mapping.
    """
    if not name:
        return "Unknown"
        
    if voice_map:
        for dn, fn in voice_map.items():
            if fn == name:
                return dn
                
    match = re.search(r", (.*Neural)\)$", name)
    return match.group(1) if match else name
