"""Browser entry point for pygbag. Desktop runs it too: `python main.py`."""

import asyncio

# pygbag picks wheels by scanning this file's imports; tilebase imports
# pygame lazily, so name it here or the browser gets an empty module.
import pygame  # noqa: F401

from tilebase.play import run

asyncio.run(run())
