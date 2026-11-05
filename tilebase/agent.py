"""One tool. The model places the 64 by 64 box and cannot do anything else."""

from __future__ import annotations

import base64
import http.client
import json
import os
from dataclasses import dataclass
from pathlib import Path

MODEL = "google/gemini-3.5-flash-lite"

SYSTEM = (
    "You place one box on the level in the image. "
    "The image is the entire level, 30 tiles wide and 9 tiles tall. "
    "Each tile is 32 by 32 pixels. The box is 64 by 64 pixels, two tiles by two tiles. "
    "You have one tool, place_box. col and row are the top-left tile. "
    "Column 0 is the left edge. Row 0 is the top. Rows grow downward. "
    "Stone, the wooden bridge, the crate, and the barred door are solid. "
    "The gold platform can be jumped up through. Spikes kill. The green flag is the exit. "
    "Pale blue ice is solid and slippery. The red spring on a coil is solid and bounces you high. "
    "Glowing orange-red lava kills on touch. Brown cracked rock is solid but falls when stood on. "
    "The orange square is the box if it is already placed. The character is the player. "
    "Put the box on the thing the player names. "
    "The floor is the bottom row, so covering a floor tile uses the row above it. "
    "If they do not name a place, cover the spikes. "
    "Do not cover the player or the exit. Call the tool once."
)


@dataclass(frozen=True)
class Placed:
    col: int
    row: int


@dataclass(frozen=True)
class AgentMiss:
    message: str


def api_key() -> str | None:
    value = os.environ.get("OPENROUTER_API_KEY")
    if value:
        return value
    env_file = Path(__file__).resolve().parents[1] / ".env.local"
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw = line.split("=", 1)
        if name.strip() == "OPENROUTER_API_KEY":
            return raw.strip().strip('"').strip("'")
    return None


def ask(prompt: str, level_png: bytes) -> Placed | AgentMiss:
    """Send the player's sentence and a PNG of the whole level. Return the tool's tile."""
    key = api_key()
    if key is None:
        return AgentMiss("OPENROUTER_API_KEY is missing")
    payload = {
        "model": MODEL,
        "temperature": 0,
        "reasoning": {"effort": "medium"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(level_png).decode()
                        },
                    },
                ],
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "place_box",
                    "description": "Place the 64x64 box. col and row are its top-left tile.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "col": {"type": "integer"},
                            "row": {"type": "integer"},
                        },
                        "required": ["col", "row"],
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "place_box"}},
    }
    conn = http.client.HTTPSConnection("openrouter.ai", timeout=45)
    conn.request(
        "POST",
        "/api/v1/chat/completions",
        json.dumps(payload),
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-Title": "Grok the Gap",
        },
    )
    response = conn.getresponse()
    raw = response.read().decode()
    if response.status != 200:
        return AgentMiss(f"model {response.status}: {raw[:180]}")
    data = json.loads(raw)
    message = data["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if not calls:
        return AgentMiss("the model did not place the box")
    function = calls[0].get("function") or {}
    if function.get("name") != "place_box":
        return AgentMiss("the model called a different tool")
    arguments = function.get("arguments")
    parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
    if not isinstance(parsed, dict):
        return AgentMiss("place_box arguments were not an object")
    col = parsed.get("col")
    row = parsed.get("row")
    if not isinstance(col, int) or not isinstance(row, int):
        return AgentMiss("place_box needs integer col and row")
    return Placed(col, row)


@dataclass(frozen=True)
class PlacedPlatform:
    slot: str
    col: int
    row: int


PLATFORM_SYSTEM = (
    "You place one platform from your pocket onto the level in the image. "
    "The image is the entire level, 30 tiles wide and 17 tiles tall. "
    "Each tile is 32 by 32 pixels. "
    "Your pocket holds two platforms, named left and right. "
    "Each is 4 tiles wide and 1 tile tall. col and row are the top-left tile. "
    "Column 0 is the left edge. Row 0 is the top. Rows grow downward. "
    "You have one tool, place_platform. slot is left or right. "
    "Stone is solid. Pale blue ice is solid and slippery. "
    "Spikes kill. The green flag is the exit. "
    "A grey bar is a platform you already placed. "
    "The stone bridge on row 5 is broken. "
    "The left gap starts at column 6. The right gap starts at column 14. "
    "Put the platform on the place the player names. "
    "If they do not name a place, fill the gap that platform fits: "
    "left at column 6 row 5, right at column 14 row 5. "
    "If they name a slot, use that slot. "
    "Do not cover the player or the flag. Call the tool once."
)


def ask_platforms(prompt: str, level_png: bytes) -> PlacedPlatform | AgentMiss:
    """Place one pocket platform. The yard's box tool is unchanged."""
    key = api_key()
    if key is None:
        return AgentMiss("OPENROUTER_API_KEY is missing")
    payload = {
        "model": MODEL,
        "temperature": 0,
        "reasoning": {"effort": "medium"},
        "messages": [
            {"role": "system", "content": PLATFORM_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(level_png).decode()
                        },
                    },
                ],
            },
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "place_platform",
                    "description": (
                        "Place one pocket platform. "
                        "slot is left or right. col and row are its left tile."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "slot": {"type": "string", "enum": ["left", "right"]},
                            "col": {"type": "integer"},
                            "row": {"type": "integer"},
                        },
                        "required": ["slot", "col", "row"],
                    },
                },
            }
        ],
        "tool_choice": {"type": "function", "function": {"name": "place_platform"}},
    }
    conn = http.client.HTTPSConnection("openrouter.ai", timeout=45)
    conn.request(
        "POST",
        "/api/v1/chat/completions",
        json.dumps(payload),
        {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-Title": "Grok the Gap",
        },
    )
    response = conn.getresponse()
    raw = response.read().decode()
    if response.status != 200:
        return AgentMiss(f"model {response.status}: {raw[:180]}")
    data = json.loads(raw)
    message = data["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if not calls:
        return AgentMiss("the model did not place a platform")
    function = calls[0].get("function") or {}
    if function.get("name") != "place_platform":
        return AgentMiss("the model called a different tool")
    arguments = function.get("arguments")
    parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
    if not isinstance(parsed, dict):
        return AgentMiss("place_platform arguments were not an object")
    slot = parsed.get("slot")
    col = parsed.get("col")
    row = parsed.get("row")
    if slot not in ("left", "right"):
        return AgentMiss("place_platform slot must be left or right")
    if isinstance(col, float) and col.is_integer():
        col = int(col)
    if isinstance(row, float) and row.is_integer():
        row = int(row)
    if not isinstance(col, int) or not isinstance(row, int):
        return AgentMiss("place_platform needs integer col and row")
    return PlacedPlatform(slot, col, row)
