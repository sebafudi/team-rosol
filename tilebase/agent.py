"""One tool. The model places one of the contraptions in stock and cannot do anything else."""

from __future__ import annotations

import base64
import http.client
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from tilebase.contraptions import Stock, available, describe, contraption


@dataclass(frozen=True)
class Provider:
    host: str
    path: str
    key_name: str
    model: str
    extra: dict


# xAI direct skips the OpenRouter hop. The non-reasoning Grok still sees images.
PROVIDERS = {
    "xai": Provider(
        "api.x.ai", "/v1/chat/completions", "XAI_API_KEY", "grok-4.20-non-reasoning", {}
    ),
    "openrouter": Provider(
        "openrouter.ai",
        "/api/v1/chat/completions",
        "OPENROUTER_API_KEY",
        "google/gemini-3.5-flash-lite",
        {"reasoning": {"effort": "medium"}},
    ),
}

SYSTEM = (
    "You place one contraption on the level. "
    "You get an image of the entire level, 30 tiles wide and 9 tall, and the same level as a text grid. "
    "The grid is exact: take every col and row from it, never from pixel positions in the image. "
    "Each grid character is one tile. The ruler above the rows gives the column, and the label before a row gives the row. "
    "Column 0 is the left edge. Row 0 is the top. Rows grow downward. "
    "Contraptions are one-time use: the user message lists the ones still left. "
    "You have one tool, place_contraption. name picks the contraption. "
    "col and row are its top-left tile, and it covers the width and height listed for it from there. "
    "Every tile it covers must be air (.) or spikes (^) or lava (L). "
    "It can never cover stone, a bridge, a platform, a crate, a door, a spring, cracked rock, the exit (E), or the player (P). "
    "Check each covered tile in the grid before you answer. "
    "Spikes and lava kill. The gold platform can be jumped up through. Ice is solid and slippery. "
    "The spring is solid and bounces the player high. Cracked rock falls when stood on. "
    "Pick the contraption that fits what the player asks for and put it on the thing they name. "
    "To cover something on the floor, put the contraption in the row above the floor. "
    "Unless the player asks for the air, rest the contraption on the floor or on a solid tile, not floating. "
    "The grid is followed by every named tile run with its row and columns: use those numbers. "
    "If they do not name a place or a contraption, cover the spikes with whatever fits. "
    "Call the tool once."
)


def tool(stock: Stock) -> dict:
    """The one tool. `name` can only be a contraption still in stock."""
    return {
        "type": "function",
        "function": {
            "name": "place_contraption",
            "description": "Place one contraption. col and row are its top-left tile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": [c.id for c in available(stock)]},
                    "col": {"type": "integer"},
                    "row": {"type": "integer"},
                },
                "required": ["name", "col", "row"],
            },
        },
    }


@dataclass(frozen=True)
class Placed:
    name: str
    col: int
    row: int


@dataclass(frozen=True)
class AgentMiss:
    message: str


def _setting(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    env_file = Path(__file__).resolve().parents[1] / ".env.local"
    if not env_file.is_file():
        return None
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        if key.strip() == name:
            return raw.strip().strip('"').strip("'")
    return None


def provider() -> Provider:
    """AGENT_PROVIDER picks the backend, AGENT_MODEL overrides its model."""
    name = _setting("AGENT_PROVIDER") or ("xai" if _setting("XAI_API_KEY") else "openrouter")
    chosen = PROVIDERS.get(name, PROVIDERS["openrouter"])
    model = _setting("AGENT_MODEL")
    if model:
        return Provider(chosen.host, chosen.path, chosen.key_name, model, chosen.extra)
    return chosen


_lock = threading.Lock()
_idle: dict[str, list[http.client.HTTPSConnection]] = {}


def _take(host: str) -> http.client.HTTPSConnection:
    with _lock:
        pool = _idle.setdefault(host, [])
        if pool:
            return pool.pop()
    return http.client.HTTPSConnection(host, timeout=45)


def _give(host: str, conn: http.client.HTTPSConnection) -> None:
    with _lock:
        _idle.setdefault(host, []).append(conn)


def _post(host: str, path: str, body: bytes, headers: dict) -> tuple[int, str]:
    """POST over a kept-alive connection so TLS is paid once, not per command.

    Connections are pooled so a speculative call and the real one can overlap.
    """
    for attempt in (0, 1):
        conn = _take(host)
        try:
            conn.request("POST", path, body, headers)
            response = conn.getresponse()
            result = response.status, response.read().decode()
        except (http.client.HTTPException, OSError):
            conn.close()
            if attempt:
                raise
            continue
        _give(host, conn)
        return result
    raise RuntimeError("unreachable")


def warm() -> None:
    """Open the TLS connection ahead of the first command."""
    host = provider().host
    conn = _take(host)
    try:
        conn.connect()
    except OSError:
        conn.close()
        return
    _give(host, conn)


def ask(prompt: str, level_png: bytes, grid: str, stock: Stock) -> Placed | AgentMiss:
    """Send the whole level as a PNG and a coordinate grid, the stock left, and the player's sentence."""
    if not stock:
        return AgentMiss("no contraptions left")
    chosen = provider()
    key = _setting(chosen.key_name)
    if key is None:
        return AgentMiss(f"{chosen.key_name} is missing")
    image = {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64," + base64.b64encode(level_png).decode()},
    }
    payload = {
        "model": chosen.model,
        "temperature": 0,
        **chosen.extra,
        # Image before text: the unchanged level is a cacheable prefix.
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    image,
                    {"type": "text", "text": f"Grid:\n{grid}\n\nLeft: {describe(stock)}.\n{prompt}"},
                ],
            },
        ],
        "tools": [tool(stock)],
        "tool_choice": {"type": "function", "function": {"name": "place_contraption"}},
    }
    try:
        status, raw = _post(
            chosen.host,
            chosen.path,
            json.dumps(payload).encode(),
            {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Title": "Grok the Gap",
            },
        )
    except (http.client.HTTPException, OSError) as error:
        return AgentMiss(f"model unreachable: {error}")
    if status != 200:
        return AgentMiss(f"model {status}: {raw[:180]}")
    data = json.loads(raw)
    message = data["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if not calls:
        return AgentMiss("the model did not place anything")
    function = calls[0].get("function") or {}
    if function.get("name") != "place_contraption":
        return AgentMiss("the model called a different tool")
    arguments = function.get("arguments")
    parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
    if not isinstance(parsed, dict):
        return AgentMiss("place_contraption arguments were not an object")
    name = parsed.get("name")
    col = parsed.get("col")
    row = parsed.get("row")
    if not isinstance(name, str) or contraption(name) is None:
        return AgentMiss("place_contraption needs a contraption name")
    if not isinstance(col, int) or not isinstance(row, int):
        return AgentMiss("place_contraption needs integer col and row")
    return Placed(name, col, row)
