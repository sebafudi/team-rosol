# Level design template

Copy this block for each level. Fill every field before building.

---

## Level ID
`L0X` — short name:

## Teaching goal
One AI verb the player must learn (pick one primary):
- [ ] move platform
- [ ] open / close path (door, gate, wall)
- [ ] place bridge / block
- [ ] remove / destroy obstacle
- [ ] other:

## Soft lock (why solo fails)
Describe the stuck state before any AI edit:

## Starting layout (ASCII or notes)
```
# = solid   P = player start   E = exit   . = air
# ? = editable named object (label below)

```

## Named editable objects
| ID | Type | Start pose | Allowed AI actions |
|----|------|------------|--------------------|
|    | platform / door / bridge / block / switch | x,y / open/closed | move / place / remove / toggle |

## Allowed AI edit space
Bounds the AI may change (tiles / rect). Anything outside is frozen.

## Intended solve (happy path)
1. Player prompt (example):
2. AI edit applied:
3. Player movement:
4. (optional second prompt:)
5. Reach exit

## Fail / reject cases
Prompts the AI should refuse or clarify (e.g. delete exit, bury player, open infinite pit):

## Win checks
- [ ] Exit reachable only after ≥1 successful AI edit
- [ ] Soft lock is readable in <5 seconds
- [ ] Demo prompt works on first try
- [ ] No soft-lock after a valid edit

## Demo beat (10–20s)
What the audience should see:

## Notes / risk
Timing, animation, or implementation gotchas:
