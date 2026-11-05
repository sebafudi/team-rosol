# Context: Co-op AI Platformer

## What we're building
A **multiplayer 2D platformer** in **pygame** where a human player and an **in-app AI agent** must cooperate to finish each level.

The player cannot clear a level alone. The map always has gaps, blocked paths, or misplaced pieces that only make sense if the AI rearranges **in-level elements** while the player moves.

## Core loop
1. Player explores a level and hits a soft lock (too high, gap too wide, door closed, platform missing).
2. Player prompts the in-app AI in natural language (e.g. "raise the left platform", "add a bridge over the pit", "open the gate").
3. AI interprets the request and **edits map items** (move / place / remove / toggle platforms, blocks, bridges, doors, switches, hazards).
4. Player uses the new layout to progress; repeat until the exit.
5. Win condition: reach the exit with both roles having mattered — player movement + at least one successful AI edit.

## Product principles
- **Cooperation is mandatory**, not cosmetic. Every level should be impossible or unfair without AI edits.
- **Edits are spatial and visible.** The AI changes concrete level objects; it does not win by teleporting the player or skipping the level.
- **Prompts stay in-app.** Chat/prompt UI lives inside the game window (or an overlay), not a separate tool.
- **Fast iteration for hackathon.** Prefer simple tile/object edits over complex physics rewrites.
- **Readable feedback.** Show what the AI changed (highlight moved tiles, short confirmation text).

## AI responsibilities
- Parse short player prompts about the current level.
- Propose and apply **safe map mutations** within allowed object types and bounds.
- Prefer the smallest edit that unblocks progress.
- Refuse or clarify when a request would break the level (delete exit, soft-lock the player forever, remove the floor under the player without a replacement).

## Player responsibilities
- Platforming: run, jump, avoid hazards.
- Decide *what* to ask the AI and *when*.
- Use the edited layout to finish the level.

## Level design rules
- Start each level with a clear **soft lock** that teaches one AI verb (move platform, open path, place bridge/block).
- Keep geometry simple: tiles, rect platforms, doors, pits, switches.
- Always leave enough space for an AI edit to create a valid path.
- Later levels can require **sequenced** prompts (move A, then place B) or timing with moving hazards.

## Tech sketch (hackathon-friendly)
- **Engine:** pygame, 2D side-view.
- **World:** tilemap or list of collidable rects / named entities.
- **AI layer:** prompt → structured edit command → apply to map entities → re-collide.
- **Multiplayer note:** "multiplayer" here means **human + AI agent** sharing one level (not necessarily online PvP). If online co-op is added later, keep the same edit API.

## Out of scope (for now)
- Full online multiplayer netcode
- Generative art / infinite procedural worlds
- Combat-heavy systems
- Voice input (text prompt is enough)

## Demo story (1 minute)
1. Show a stuck player at a gap.
2. Type a prompt; AI builds a bridge / moves a platform.
3. Player crosses and reaches the exit.
4. Call out: *you play, the AI rewires the level*.

## One-liner
**A pygame platformer where you and an in-app AI co-op: you jump, it rewrites the map mid-level from your prompts.**
