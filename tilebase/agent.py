"""One tool. The model places the 64 by 64 box and cannot do anything else."""

from __future__ import annotations

import base64
import http.client
import json
import os
from dataclasses import dataclass
from pathlib import Path

from tilebase.kinds import LEGEND

MODEL = "x-ai/grok-4.7"

SYSTEM = (
    "You place one box on a tile map. The box is 64 by 64 pixels, "
    "which is 2 tiles by 2 tiles. Tiles are 32 pixels. "
    "You have one tool, place_box. col and row are the top-left tile. "
    "Rows grow downward. "
    f"{LEGEND}. "
    "Put the box on the kind the player names. "
    "col and row are its top-left, and it also fills the next column and the next row. "
    "The floor is the bottom row, so covering a floor tile uses the row above it. "
    "If they do not name a place, cover the spikes. "
    "The image is the screen the player sees right now, before you place anything. "
    "Do not cover P or E. Call the tool once."
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


def ask(prompt: str, grid: str, frame_png: bytes) -> Placed | AgentMiss:
    """Send the player's sentence, the grid, and a PNG of the screen. Return the tool's tile."""
    key = api_key()
    if key is None:
        return AgentMiss("OPENROUTER_API_KEY is missing")
    payload = {
        "model": MODEL,
        "temperature": 0,
        "reasoning": {"effort": "minimal"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{grid}\n\nPlayer: {prompt}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(frame_png).decode()
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
