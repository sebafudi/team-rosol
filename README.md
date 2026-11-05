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

`load_map` reads a character grid. `put_cell` returns a new grid with one cell replaced. `plan_move` chooses the body's delta each frame. `move_body` applies that delta and stops on tiles the caller marks as blocking. The demo slides a rectangle with the arrow keys on 32 by 32 tiles. It does not jump.

The window is fullscreen. The camera is framed at 320 by 180 and scaled in whole pixels so that view fills 720p, 1080p, 1440p, 4K, 16:10, and ultrawide displays. Escape closes it.

## Movement sandbox

```bash
python -m tilebase.play
```

Arrows/WASD move, Space/C/Z jump (hold for height), X/Shift dash in 8 directions, R respawn, M mutes the music, F1 debug overlay. Gamepad works too (A jump, B/X dash).

Jumping, wall jumping, dashing, landing, hitting a ceiling, and falling out of the map each play a sound, and a short tune loops from the title screen on. A gap in the demo floor drops you out of the level.

`tilebase/player.py` is the pure controller: run/accel, variable jump with apex hang, coyote time, jump buffering, wall slide and wall jump, one dash charge refilled on landing. Because the hero is a ball, its corners are forgiving: it slips around ceiling corners, pops over low lips, and rolls off a ledge it barely stands on. `tilebase/blob.py` animates the hero: squash and stretch, a roll angle that follows distance travelled and rocks back eyes-up when the ball stops, and dust puffs. `tilebase/art.py` paints it with Nikolas's art from `assets/`: the Grok Bot ball (idle, jump and climb poses) spins as it rolls and turns blue when the dash is spent, tiles come from `assets/tiles/`, and `assets/bg.png` drifts behind the level as parallax. All movement numbers live in `player.Tuning`.
