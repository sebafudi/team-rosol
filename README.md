# team-rosol

Tile scaffold for a pygame game. A platformer, and the in-app AI that rewrites the map, sit on top of this package.

```bash
pip install -r requirements.txt
python -m tilebase
```

`load_map` reads a character grid. `put_cell` returns a new grid with one cell replaced. `plan_move` chooses the body's delta each frame. `move_body` applies that delta and stops on tiles the caller marks as blocking. The demo slides a rectangle with the arrow keys on 32 by 32 tiles. It does not jump.

## Movement sandbox

```bash
python -m tilebase.play
```

Arrows/WASD move, Space/C/Z jump (hold for height), X/Shift dash in 8 directions, R respawn, F1 debug overlay. Gamepad works too (A jump, B/X dash).

`tilebase/player.py` is the pure controller: run/accel, variable jump with apex hang, coyote time, jump buffering, wall slide and wall jump, one dash charge refilled on landing. Because the hero is a ball, its corners are forgiving: it slips around ceiling corners, pops over low lips, and rolls off a ledge it barely stands on. `tilebase/blob.py` draws the placeholder jelly ball: squash and stretch, eyes that follow input and blink, and dust puffs. All numbers live in `player.Tuning`.
