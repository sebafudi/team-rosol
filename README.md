# team-rosol

Tile scaffold for a pygame game. A platformer, and the in-app AI that rewrites the map, sit on top of this package.

```bash
pip install -r requirements.txt
python -m tilebase
```

`load_map` reads a character grid. `put_cell` returns a new grid with one cell replaced. `plan_move` chooses the body's delta each frame. `move_body` applies that delta and stops on tiles the caller marks as blocking. The demo slides a rectangle with the arrow keys on 32 by 32 tiles. It does not jump.

The window is fullscreen. The camera is framed at 320 by 180 and scaled in whole pixels so that view fills 720p, 1080p, 1440p, 4K, 16:10, and ultrawide displays. Escape closes it.
