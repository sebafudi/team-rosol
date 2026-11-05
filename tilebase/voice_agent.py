"""Cascading voice agent: mic → Deepgram → parse stages → edit API.

Stages run cheapest-first. Each successful parse attempt charges the credit
ledger; failures fall through to the next stage. Testing uses an infinite
ledger so demos never run dry.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, replace

from tilebase.credits import (
    InsufficientCredits,
    Ledger,
    charge,
    remaining,
    testing_ledger,
)
from tilebase.edit import Command, EditResult, EditSuccess, Entities, apply_edit, entities_by_type
from tilebase.edit_integration import (
    EditState,
    apply_pending_edits,
    create_edit_state,
    prompt_to_command,
    queue_edit,
)
from tilebase.speech import ListenError, Transcript, listen


ParseFn = Callable[[str, Entities], Command | None]


@dataclass(frozen=True)
class Stage:
    name: str
    cost: int
    parse: ParseFn


@dataclass(frozen=True)
class AgentOk:
    command: Command
    stage: str
    ledger: Ledger


@dataclass(frozen=True)
class AgentMiss:
    ledger: Ledger
    reason: str


@dataclass(frozen=True)
class AgentBroke:
    ledger: Ledger
    need: int
    have: int


AgentResult = AgentOk | AgentMiss | AgentBroke


def _leftmost(entities: Entities, type_name: str):
    items = entities_by_type(entities, type_name)
    if not items:
        return None
    return min(items, key=lambda e: min(c for c, _ in e.tiles))


def _rightmost(entities: Entities, type_name: str):
    items = entities_by_type(entities, type_name)
    if not items:
        return None
    return max(items, key=lambda e: max(c for c, _ in e.tiles))


def _first(entities: Entities, type_name: str):
    items = entities_by_type(entities, type_name)
    return items[0] if items else None


def _rules_stage(prompt: str, entities: Entities) -> Command | None:
    """Reuse the integration stub (raise left / lower right / open door)."""
    return prompt_to_command(prompt, entities)


def _phrase_stage(prompt: str, entities: Entities) -> Command | None:
    """Broader keyword cascade for spoken prompts."""
    text = prompt.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)

    if any(w in text for w in ("raise", "lift", "up", "higher")):
        target = None
        if "right" in text:
            target = _rightmost(entities, "platform")
        else:
            target = _leftmost(entities, "platform") or _first(entities, "platform")
        if target:
            steps = 2 if any(w in text for w in ("more", "higher", "lot")) else 1
            return Command(op="move", id=target.id, by=(0, -steps))

    if any(w in text for w in ("lower", "drop", "down", "sink")):
        target = None
        if "left" in text:
            target = _leftmost(entities, "platform")
        else:
            target = _rightmost(entities, "platform") or _first(entities, "platform")
        if target:
            steps = 2 if any(w in text for w in ("more", "lower", "lot")) else 1
            return Command(op="move", id=target.id, by=(0, steps))

    if any(w in text for w in ("open", "unlock")) and any(
        w in text for w in ("door", "gate")
    ):
        door = _first(entities, "door") or _first(entities, "gate")
        if door and not door.open:
            return Command(op="toggle", id=door.id)

    if any(w in text for w in ("close", "shut", "lock")) and any(
        w in text for w in ("door", "gate")
    ):
        door = _first(entities, "door") or _first(entities, "gate")
        if door and door.open:
            return Command(op="toggle", id=door.id)

    if any(w in text for w in ("remove", "delete", "clear")) and "platform" in text:
        target = _leftmost(entities, "platform") if "left" in text else (
            _rightmost(entities, "platform") if "right" in text else _first(entities, "platform")
        )
        if target:
            return Command(op="remove", id=target.id)

    return None


def _id_stage(prompt: str, entities: Entities) -> Command | None:
    """Last resort: spoken entity id + verb."""
    text = prompt.lower().strip()
    for entity in entities.items:
        if entity.id.lower() not in text and entity.id.lower().replace("_", " ") not in text:
            continue
        if any(w in text for w in ("raise", "up", "lift")):
            return Command(op="move", id=entity.id, by=(0, -1))
        if any(w in text for w in ("lower", "down", "drop")):
            return Command(op="move", id=entity.id, by=(0, 1))
        if any(w in text for w in ("open", "close", "toggle")) and entity.type in (
            "door",
            "gate",
        ):
            return Command(op="toggle", id=entity.id)
        if any(w in text for w in ("remove", "delete")):
            return Command(op="remove", id=entity.id)
    return None


CASCADE: tuple[Stage, ...] = (
    Stage("rules", cost=1, parse=_rules_stage),
    Stage("phrase", cost=3, parse=_phrase_stage),
    Stage("id", cost=5, parse=_id_stage),
)


def resolve_prompt(
    prompt: str,
    entities: Entities,
    ledger: Ledger,
    stages: tuple[Stage, ...] = CASCADE,
) -> AgentResult:
    """Run cascade stages until one yields a Command, charging each attempt."""
    current = ledger
    for stage in stages:
        billed = charge(
            current,
            stage.cost,
            reason=f"parse:{prompt[:48]}",
            stage=stage.name,
        )
        if isinstance(billed, InsufficientCredits):
            return AgentBroke(ledger=current, need=billed.need, have=billed.have)
        current = billed.ledger
        command = stage.parse(prompt, entities)
        if command is not None:
            return AgentOk(command=command, stage=stage.name, ledger=current)
    return AgentMiss(ledger=current, reason="no stage matched the prompt")


@dataclass(frozen=True)
class VoiceSession:
    state: EditState
    ledger: Ledger


def apply_voice_command(session: VoiceSession, result: AgentOk) -> tuple[VoiceSession, EditResult]:
    queued = queue_edit(session.state, result.command)
    state, results = apply_pending_edits(queued)
    edit = results[0] if results else EditSuccess(state.world, state.entities, frozenset())
    return VoiceSession(state=state, ledger=result.ledger), edit


def demo_world() -> EditState:
    """Small named-entity map for voice demos (same layout as integration_demo)."""
    from tilebase.art import tile_drawer
    from tilebase.edit import Entity, define_entities
    from tilebase.geom import Rect
    from tilebase.tiles import World, define, load_map

    tile = 32
    loaded = load_map(
        (
            "####################",
            "#..................#",
            "#..................#",
            "#..................#",
            "#...####.......##..#",
            "#..................#",
            "#..................#",
            "####################",
        ),
        (
            define(".", id="empty", draw=lambda s, r: None, marks=frozenset()),
            define(
                "#",
                id="solid",
                draw=tile_drawer("solid"),
                marks=frozenset({"blocks"}),
            ),
        ),
        tile_size=tile,
    )
    assert isinstance(loaded, World)
    _, entities = define_entities(
        loaded,
        (
            Entity(id="plat_left", type="platform", tiles=((4, 4), (5, 4), (6, 4), (7, 4))),
            Entity(id="plat_right", type="platform", tiles=((15, 4), (16, 4))),
            Entity(id="door1", type="door", tiles=((10, 5),), open=False),
        ),
        bounds=Rect(0, 0, 20 * tile, 8 * tile),
    )
    return create_edit_state(loaded, entities)


def handle_text(session: VoiceSession, prompt: str) -> tuple[VoiceSession, str]:
    """Resolve one spoken (or typed) prompt and apply a successful edit."""
    parsed = resolve_prompt(prompt, session.state.entities, session.ledger)
    if isinstance(parsed, AgentBroke):
        return (
            replace(session, ledger=parsed.ledger),
            f"out of credits (need {parsed.need}, have {parsed.have})",
        )
    if isinstance(parsed, AgentMiss):
        return (
            replace(session, ledger=parsed.ledger),
            f"miss: {parsed.reason} [credits={remaining(parsed.ledger)}]",
        )
    session, edit = apply_voice_command(session, parsed)
    if isinstance(edit, EditSuccess):
        return (
            session,
            f"ok via {parsed.stage}: {parsed.command.op} {parsed.command.id} "
            f"by={parsed.command.by} changed={len(edit.changed_tiles)} "
            f"[credits={remaining(session.ledger)} spent={session.ledger.spent}]",
        )
    return (
        session,
        f"edit rejected ({type(edit).__name__}) via {parsed.stage} "
        f"[credits={remaining(session.ledger)}]",
    )


async def run_voice(session: VoiceSession | None = None) -> None:
    """Stream the mic; on each final transcript, cascade → edit the level."""
    current = session or VoiceSession(state=demo_world(), ledger=testing_ledger())
    print(
        f"voice agent ready (credits={remaining(current.ledger)}). "
        "say: raise the left platform / open the door. Ctrl+C to stop.",
        flush=True,
    )
    async for event in listen():
        if isinstance(event, ListenError):
            print(f"error: {event.message}", flush=True)
            return
        if not event.final:
            print(f"live: {event.text}", flush=True)
            continue
        print(f"final: {event.text}", flush=True)
        current, message = handle_text(current, event.text)
        print(message, flush=True)


def main() -> None:
    try:
        asyncio.run(run_voice())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
