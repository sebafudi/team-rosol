# Team Rosół

**You jump. The AI rewires the map.**

A 2D pygame platformer where a human player and an in-game AI share one level. You cannot finish a stage alone. The layout is always a little wrong: a pit too wide, a door shut, a platform one tile too low. You type what you need in the game window. The AI edits real objects in the world. Then you play through the new geometry.

Co-op here means **human + AI on the same map**, not online PvP.

## Why this exists

Most “AI in a game” is a chatterbot or a second shooter. We want the AI to be a **live level editor** that only acts when you ask, and only by moving things you can see.

That forces a kind of play you cannot get from a static map:

- You still have to run and jump.
- You also have to decide *what* to change and *when*.
- The win is shared. If nobody prompts, the exit stays unreachable. If the AI teleports you, it is the wrong game.

## How a level plays

1. You explore and hit a **soft lock**: a gap you cannot jump, a gate you cannot open, a path that is missing.
2. You prompt in natural language, still inside the game: *“raise the left platform”*, *“bridge the pit”*, *“open the gate”*.
3. The AI applies the smallest safe edit: move, place, remove, or toggle a named object.
4. The change is visible (highlight + a short confirmation). Collision updates. You use the new layout.
5. Repeat until you reach the exit. A clear requires **player movement and at least one successful AI edit**.

```
#  ground     ~  pit     P  you     E  exit

Before                          After "bridge the pit"
##########################      ##########################
P          ~~~~~~       E       P     ##########        E
##########################      ##########################
           too wide                        you jump it
```

## How we get there

Hackathon time is short, so the stack stays small and the AI stays bounded.

**Engine.** pygame, side-view, 2D. The world is tiles or collidable rects plus a handful of **named editable objects** (platforms, doors, bridges, blocks, switches). Physics stays ordinary. The interesting part is mutation, not a new engine.

**AI pipeline.** Player prompt → structured edit command → apply to allowed objects → re-collide → show what changed. The model does not “win the level”. It proposes a map edit inside a sandbox: allowed object types, allowed actions, allowed bounds. It prefers the smallest change that unblocks you. It refuses edits that delete the exit, bury the player, or leave the map unplayable.

**Prompt UI.** Chat lives in the game window (or an overlay). No separate tool, no voice, no second screen.

**Levels.** Each stage teaches **one AI verb** first (move a platform, open a path, place a bridge, remove a block). Geometry stays readable in a few seconds. Later stages can sequence two prompts or add timing. We design from a shared template in [`level-design-template.md`](level-design-template.md) so every level has a soft lock, a demo prompt, and a known fail set.

**Feedback.** If the AI moved a platform, you see that platform move. The jury should never have to guess whether the model did anything.

## Run the tile scaffold

The `tilebase` package is that engine base. A platformer, and the in-app AI that rewrites the map, sit on top of it.

```bash
pip install -r requirements.txt
python -m tilebase
```

`load_map` reads a character grid. `put_cell` returns a new grid with one cell replaced. `plan_move` chooses the body's delta each frame. `move_body` applies that delta and stops on tiles the caller marks as blocking. The demo slides a rectangle with the arrow keys. It does not jump.

## What we will demo (about one minute)

1. Player stuck at a gap.
2. Type a prompt. AI builds a bridge or raises a platform.
3. Player crosses and reaches the exit.
4. Line to leave in the room: *you play, the AI rewires the level*.

## In scope / out of scope

We are shipping a playable co-op loop, not a full game.

| We build | We skip (for now) |
| --- | --- |
| pygame platforming | Online multiplayer netcode |
| In-game prompt + map edits | Voice input |
| A few authored levels | Infinite procedural worlds |
| Safe, visible mutations | Combat systems |
| Highlight + confirmation text | Generative art pipelines |

The product brief with principles and constraints is in [`context.md`](context.md).

## For the jury

Work in this repo is committed in small, atomic steps during the event. `git log` is the build history: one concern per commit, pushed as we go, not rewritten.
