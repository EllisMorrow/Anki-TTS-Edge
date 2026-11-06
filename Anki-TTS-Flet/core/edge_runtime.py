import asyncio
import importlib
from types import ModuleType


async def load_edge_tts() -> ModuleType:
    # Loading the HTTP/TLS stack must not hold up the first frame or UI events.
    # import_module retains Python's normal module cache and import locking.
    return await asyncio.to_thread(importlib.import_module, "edge_tts")
