# Team Rosół

**You jump. The AI rewires the map.**

A 2D pygame platformer where a human player and an in-game AI share one level. You cannot finish a stage alone. The layout is always a little wrong: a pit too wide, a door shut, a platform one tile too low. You type what you need in the game window. The AI edits real objects in the world. Then you play through the new geometry.

Co-op here means **human + AI on the same map**, not online PvP.

## Right now

These three frames are the browser build of the current game (`scripts/build_web.sh --serve`, then http://localhost:8000). The same screens are what `python -m tilebase.play` opens on the desktop. The AI edit described further down is the goal. What launches today is this title screen and this map.

![Title screen on the painted hills](docs/screenshots/title.png)

![The ball on the left floor, with the gap in the middle](docs/screenshots/ground.png)

![Falling through the open floor](docs/screenshots/fall.png)

Enter, Space, or a click on **Play** leaves the title. The ball starts on the left. Five floor tiles are missing in the middle. Drop through that hole and you come back on the left.

## Demo walkthrough

The YARD level, recorded from the real game (desktop build, live Grok calls). Each line is typed into the in-game prompt box; the AI places a plank on the lava, a second plank, the crate on the spikes and the step in the gap. The ball then bounces off the spring, crosses, and the game says **you made it**. Full video: [`docs/demo/walkthrough.mp4`](docs/demo/walkthrough.mp4).

![YARD walkthrough](docs/demo/walkthrough.gif)

| Prompt typed in game | Two planks bridge the lava | Exit reached |
| --- | --- | --- |
| ![Prompt box](docs/demo/prompt.png) | ![Planks over lava](docs/demo/planks.png) | ![You made it](docs/demo/cleared.png) |

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

## Run it

```bash
pip install -r requirements.txt
python -m tilebase.play
```

The window is captioned **Grok the Gap**. The view is 640 by 360 and scaled up to the window. The title screen comes first. Escape quits.

Arrows or WASD move. Space, C, or Z jumps, and holding the key jumps higher. X or Shift dashes in eight directions. R respawns. M mutes the music. F1 toggles a debug readout. A gamepad works too: A jumps, B or X dashes.

Jumping, wall jumping, dashing, landing, hitting a ceiling, and falling out of the map each play a sound, and a short tune loops from the title screen on. The map is the 20 by 9 demo grid. A five-tile hole in the floor is open. Falling through it plays the death sound and puts you back on the left.

`tilebase/player.py` is the pure controller: run/accel, variable jump with apex hang, coyote time, jump buffering, wall slide and wall jump, one dash charge refilled on landing. Because the hero is a ball, its corners are forgiving: it slips around ceiling corners, pops over low lips, and rolls off a ledge it barely stands on. `tilebase/blob.py` animates the hero: squash and stretch, a roll angle that follows distance travelled and rocks back eyes-up when the ball stops, and dust puffs. `tilebase/art.py` paints it with Nikolas's art from `assets/`: the Grok Bot ball (idle, jump and climb poses) spins as it rolls and turns blue when the dash is spent, tiles come from `assets/tiles/`, and `assets/bg.png` drifts behind the level as parallax. All movement numbers live in `player.Tuning`.

## Tile scaffold

```bash
python -m tilebase
```

Same title, then a fullscreen window. The camera is framed at 320 by 180 and scaled in whole pixels so that view fills 720p, 1080p, 1440p, 4K, 16:10, and ultrawide displays. Arrow keys slide a rectangle across the same grid. It does not jump.

`load_map` reads a character grid. `put_cell` returns a new grid with one cell replaced. `plan_move` chooses the body's delta each frame. `move_body` applies that delta and stops on tiles the caller marks as blocking.

## Play in the browser

The screenshots above are this page, from the current play loop. The web build can lag behind the desktop game while people are still changing it, so rebuild before a demo.

```bash
pip install pygbag
scripts/build_web.sh --serve   # then open http://localhost:8000
```

pygbag compiles nothing: it ships the Python sources with a WebAssembly CPython and pygame-ce. `main.py` is the browser entry point, and the game loops `await asyncio.sleep(0)` each frame so the page can draw. The script copies only `main.py`, `tilebase/` and `assets/` into the bundle, so `.env.local` never goes public. Speech input (`tilebase/speech.py`) is desktop-only for now. `scripts/build_web.sh` without `--serve` writes a static site to `build/grok-the-gap/build/web` for any static host.
