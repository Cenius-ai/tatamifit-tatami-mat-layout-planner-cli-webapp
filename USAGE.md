# Using TatamiFit

TatamiFit answers one question: *given a rectangular room, which whole-mat tatami layout
looks best?* It prints the winner as an ASCII plan and up to three ranked alternatives.

## 1. One interactive session

```sh
python3 tatamifit.py
```

Type the room width in metres, press Enter, type the depth, press Enter. TatamiFit then
shows the room it accepted and the usable grid it snapped it to:

```
Room: 3.70 m x 2.90 m -> usable grid 8 x 6 half-units (3.64 m x 2.73 m),
      0.03 m to each side wall, 0.085 m to each end wall
Plan this room? [Enter=plan, w=width, d=depth]:
```

- **Enter** plans the room.
- **w** re-asks only the width; **d** re-asks only the depth. At that prompt the previous
  answer is shown in brackets — `Width (m) [3.70]: ` — and a bare Enter keeps it, so a
  typo never costs you the other dimension.

## 2. Piping a room in (scriptable)

Both answers plus the confirm line can come from stdin, which makes the tool pipeline
friendly:

```sh
printf '3.64\n2.73\n\n' | python3 tatamifit.py
echo -e "4.10\n3.20\n\n" | python3 tatamifit.py
```

The last empty line is the confirm. Output goes to stdout, so it can be redirected to a
file or catted into a report. No colour or control characters are ever emitted.

## 3. Reading the plan page

```
+----------------+
|H1......H2......|
|................|
|H3......H4......|
|................|
+----------------+
H = long-along-width, V = long-along-depth
```

- Each half-unit of the grid is two characters wide and one line tall.
- `.` is tatami floor, spaces are floor left bare.
- `H1..Hn` are mats whose long 1.82 m side runs along the room **w**idth; `V1..Vn` are
  mats whose long side runs along the room **d**epth. Labels are numbered in reading
  order (top to bottom, left to right within each orientation).
- The frame is the room wall. The centring remainder between the wall and the grid edge
  is reported in the summary as the per-wall margin.

The summary block reports the room, the margins, the mat count and mix, the covered and
uncovered areas, the two symmetry scores and the score itself, followed by the ranking
table and the fixed weights.

## 4. How arrangements are scored

```
score = 0.50 * coverage + 0.30 * symmetry + 0.20 * margin balance
```

- **coverage** — covered mat area over the real room area.
- **symmetry** — the fraction of mat area that mirrors onto mat area about the room's
  left-right and top-bottom centre axes, averaged. Because the grid is centred, the
  leftover strip at each wall counts on both sides.
- **margin balance** — 1.00 when all four wall margins are equal, falling away as they
  diverge, so a layout that leaves one wall conspicuously bare scores lower.

Ties break by score, then by uncovered area, then by more H mats, then by first label —
a total order, so the same room always prints exactly the same table.

## 5. Refusals and exit codes

```sh
$ printf '1.20\n0.80\n\n' | python3 tatamifit.py ; echo "exit $?"
Room 1.20 m x 0.80 m is too small for a single 0.91 m x 1.82 m tatami.
exit 2
```

| Code | Meaning |
|------|---------|
| 0 | a plan was printed |
| 1 | no plan produced (Ctrl-D, Ctrl-C or empty stdin at a prompt) |
| 2 | the room was refused, or an unknown option was given |

A refusal is always one sentence: no half-drawn diagram is ever printed.

## 6. If nothing is typed

On an interactive terminal, if no answer arrives at the first prompt within 20 seconds,
TatamiFit prints the usage summary and exits 0 instead of waiting forever -- useful when
the tool is started by a recorder or a script that forgot to pipe input. Piped or
redirected input (including `< /dev/null`) is never affected: an empty input still ends
the session with exit code 1.

## 7. Limits

- A room must fit at least one 0.91 m x 1.82 m tatami in one of its two orientations.
- The drawing range is 39 x 16 half-units, i.e. 17.745 m x 7.28 m; larger rooms are
  refused with one line naming that range.
- Mats are rigid: no cutting, no fractional mats, no oblique placement.

## 8. Common recipes

```sh
# A tea room, non-interactively
printf '3.64\n2.73\n\n' | python3 tatamifit.py

# Fix a mistyped depth without retyping the width
printf '3.64\n2.73\nd\n2.90\n\n' | python3 tatamifit.py

# Save the plan to a text file
printf '3.70\n2.90\n\n' | python3 tatamifit.py > plan.txt
```
