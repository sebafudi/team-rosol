"""One tool. The model places the 64 by 64 box and cannot do anything else."""

from __future__ import annotations

import http.client
import json
import os
from dataclasses import dataclass
from pathlib import Path

MODEL = "x-ai/grok-4.3"

SYSTEM = (
    "You place one box on a tile map. The box is 64 by 64 pixels, "
    "which is 2 tiles by 2 tiles. Tiles are 32 pixels. "
    "You have one tool, place_box. col and row are the top-left tile. "
    "Rows grow downward. # is solid, . is air, P is the player, E is the exit, "
    "B is the box if it is already placed. "
    "The floor gap is the dots on the bottom row, columns 4 through 11. "
    "Call place_box with row 7 and col 6, 7, or 8, so air remains on both sides of the box. "
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


def ask(prompt: str, grid: str) -> Placed | AgentMiss:
    """Send the player's sentence and the grid. Return the tool's tile, or why it missed."""
    key = api_key()
    if key is None:
        return AgentMiss("OPENROUTER_API_KEY is missing")
    payload = {
        "model": MODEL,
        "temperature": 0,
        "reasoning": {"effort": "none"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{grid}\n\nPlayer: {prompt}"},
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
