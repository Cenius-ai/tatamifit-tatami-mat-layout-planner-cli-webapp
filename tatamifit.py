#!/usr/bin/env python3
"""TatamiFit -- plan a whole-mat tatami layout for a rectangular room.

One file, standard library only, Python 3.8+.

Pipeline: read_room() -> quantise() -> candidates() -> rank() -> render().
Nothing is written to disk and nothing is fetched from the network.
"""

from __future__ import annotations

import os
import select
import sys
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP
from fractions import Fraction
from typing import Dict, List, Tuple

VERSION = "1.0.0"

# --- Geometry constants -----------------------------------------------------
UNIT_M = Decimal("0.455")        # half-unit: half the short side of a tatami
MAT_SHORT_M = Decimal("0.91")    # short side of a whole tatami
MAT_LONG_M = Decimal("1.82")     # long side of a whole tatami
MAT_SHORT_UNITS = 2              # 0.91 m in half-units
MAT_LONG_UNITS = 4               # 1.82 m in half-units
MAX_WIDTH_UNITS = 39             # 39 half-units fit across an 80-column page
MAX_DEPTH_UNITS = 16             # 16 half-units fit in an 18-row diagram
MAX_WIDTH_M = UNIT_M * MAX_WIDTH_UNITS     # 17.745 m
MAX_DEPTH_M = UNIT_M * MAX_DEPTH_UNITS     # 7.28 m
CELL_AREA_M2 = UNIT_M * UNIT_M             # 0.207025 m2

# --- Presentation constants -------------------------------------------------
LEGEND = "H = long-along-width, V = long-along-depth"
WEIGHTS_LINE = "Weights: coverage 0.50, symmetry 0.30, margin balance 0.20"
SHORTLIST_SIZE = 3
MAX_CANDIDATES = 24
MAX_LINE_WIDTH = 80
MAX_DIAGRAM_ROWS = 18
FIRST_ANSWER_TIMEOUT_S = 20.0

WIDTH_HINT = "0.91-17.745"
DEPTH_HINT = "0.91-7.28"
WIDTH_EXAMPLE = "3.64"
DEPTH_EXAMPLE = "2.73"

# --- Number formatting ------------------------------------------------------
_THREE_DP = Decimal("0.001")
_TWO_DP = Decimal("0.01")


def format_m(value: Decimal) -> str:
    """Format metres with 2 or 3 decimals: 0.03, 0.085, 0.00, 17.745."""
    quantised = Decimal(value).quantize(_THREE_DP, rounding=ROUND_HALF_UP)
    if quantised == 0:
        quantised = abs(quantised)
    whole, _, frac = "{:.3f}".format(quantised).partition(".")
    while len(frac) > 2 and frac.endswith("0"):
        frac = frac[:-1]
    return whole + "." + frac


def format_m2(value: Decimal) -> str:
    """Format an area in square metres with exactly two decimals."""
    quantised = Decimal(value).quantize(_TWO_DP, rounding=ROUND_HALF_UP)
    if quantised == 0:
        quantised = abs(quantised)
    return "{:.2f}".format(quantised)


def format_score(value: Fraction) -> str:
    """Format a normalised 0..1 score with exactly two decimals."""
    return "{:.2f}".format(float(value))


def wrap_line(text: str, width: int = MAX_LINE_WIDTH) -> str:
    """Break a sentence onto a second line rather than exceed the width cap."""
    if len(text) <= width:
        return text
    cut = text.rfind(" ", 0, width + 1)
    if cut <= 0:
        return text
    return text[:cut] + "\n" + text[cut + 1:]


# --- Room -------------------------------------------------------------------


class PlanAborted(Exception):
    """stdin ended (Ctrl-D) or the user interrupted (Ctrl-C) at a prompt."""


class RoomRefused(Exception):
    """The room cannot be planned; the message is the one explanatory line."""


class PromptIdle(Exception):
    """A terminal was attached but nothing was typed before the fallback window."""


@dataclass(frozen=True)
class Room:
    """A confirmed room plus the centred 0.455 m sub-grid it is snapped to."""

    width_m: Decimal
    depth_m: Decimal
    width_units: int
    depth_units: int
    offset_x_m: Decimal
    offset_y_m: Decimal

    @property
    def usable_width_m(self) -> Decimal:
        return UNIT_M * self.width_units

    @property
    def usable_depth_m(self) -> Decimal:
        return UNIT_M * self.depth_units

    @property
    def room_area_m2(self) -> Decimal:
        return self.width_m * self.depth_m

    @property
    def usable_area_m2(self) -> Decimal:
        return self.usable_width_m * self.usable_depth_m


def fits_one_mat(width_units: int, depth_units: int) -> bool:
    """True when a single 4x2 or 2x4 half-unit tatami fits on the grid."""
    laid_along_width = width_units >= MAT_LONG_UNITS and depth_units >= MAT_SHORT_UNITS
    laid_along_depth = width_units >= MAT_SHORT_UNITS and depth_units >= MAT_LONG_UNITS
    return laid_along_width or laid_along_depth


def quantise(width_m: Decimal, depth_m: Decimal) -> Room:
    """Snap a room to the centred half-unit grid, or refuse it with one line."""
    width_units = int((width_m / UNIT_M).to_integral_value(rounding=ROUND_FLOOR))
    depth_units = int((depth_m / UNIT_M).to_integral_value(rounding=ROUND_FLOOR))
    if not fits_one_mat(width_units, depth_units):
        raise RoomRefused(wrap_line(
            "Room {} m x {} m is too small for a single {} m x {} m tatami.".format(
                format_m(width_m), format_m(depth_m),
                format_m(MAT_SHORT_M), format_m(MAT_LONG_M))))
    if (width_m > MAX_WIDTH_M or depth_m > MAX_DEPTH_M
            or width_units > MAX_WIDTH_UNITS or depth_units > MAX_DEPTH_UNITS):
        raise RoomRefused(wrap_line(
            "Room {} x {} m exceeds the {} x {} half-unit range ({} x {} m).".format(
                format_m(width_m), format_m(depth_m),
                MAX_WIDTH_UNITS, MAX_DEPTH_UNITS,
                format_m(MAX_WIDTH_M), format_m(MAX_DEPTH_M))))
    offset_x_m = (width_m - width_units * UNIT_M) / 2
    offset_y_m = (depth_m - depth_units * UNIT_M) / 2
    return Room(width_m, depth_m, width_units, depth_units, offset_x_m, offset_y_m)


def preview_line(room: Room) -> str:
    """The accepted-room line: the room, the snapped grid and the wall gaps.

    Wrapped onto a second line when the sentence would break the 80-column cap.
    """
    head = (
        "Room: {} m x {} m -> usable grid {} x {} half-units ({} m x {} m),".format(
            format_m(room.width_m), format_m(room.depth_m),
            room.width_units, room.depth_units,
            format_m(room.usable_width_m), format_m(room.usable_depth_m),
        )
    )
    tail = "{} m to each side wall, {} m to each end wall".format(
        format_m(room.offset_x_m), format_m(room.offset_y_m))
    if len(head) + 1 + len(tail) <= MAX_LINE_WIDTH:
        return head + " " + tail
    return head + "\n" + "      " + tail


# --- Mats and arrangements --------------------------------------------------
Placement = Tuple[int, int, str]       # (x, y, orientation) on the half-unit grid
Packing = Tuple[Placement, ...]        # a full candidate, canonical order


@dataclass(frozen=True)
class Mat:
    """One whole tatami at an integer half-unit position."""

    x: int
    y: int
    orientation: str                   # "H" = long side along the width, "V" = along the depth
    label: str = ""

    @property
    def w_units(self) -> int:
        return MAT_LONG_UNITS if self.orientation == "H" else MAT_SHORT_UNITS

    @property
    def h_units(self) -> int:
        return MAT_SHORT_UNITS if self.orientation == "H" else MAT_LONG_UNITS

    @property
    def covered_m2(self) -> Decimal:
        return CELL_AREA_M2 * self.w_units * self.h_units


@dataclass(frozen=True)
class Arrangement:
    """One scored candidate layout."""

    ident: str
    mats: Tuple[Mat, ...]
    margins_m: Dict[str, Decimal]
    symmetry_lr: Fraction
    symmetry_tb: Fraction
    grid_cells: int
    covered_cells: int
    covered_m2: Decimal
    uncovered_m2: Decimal
    coverage: Fraction
    margin_balance: Fraction
    score: Fraction
    note: str = ""

    @property
    def h_count(self) -> int:
        return sum(1 for mat in self.mats if mat.orientation == "H")

    @property
    def v_count(self) -> int:
        return len(self.mats) - self.h_count

    @property
    def mixed(self) -> bool:
        return self.h_count > 0 and self.v_count > 0

    @property
    def symmetry(self) -> Fraction:
        return (self.symmetry_lr + self.symmetry_tb) / 2

    @property
    def full_coverage(self) -> bool:
        return self.covered_cells > 0 and self.covered_cells == self.grid_cells

    @property
    def mix_label(self) -> str:
        return "{}H+{}V".format(self.h_count, self.v_count)


# --- Packing primitives -----------------------------------------------------


def mat_size(orientation: str) -> Tuple[int, int]:
    """Return (width_units, depth_units) of a tatami in the given orientation."""
    if orientation == "H":
        return MAT_LONG_UNITS, MAT_SHORT_UNITS
    return MAT_SHORT_UNITS, MAT_LONG_UNITS


def canonical(placements: Sequence[Placement]) -> Packing:
    """Sort a packing by reading order (smallest y, then smallest x)."""
    return tuple(sorted(placements, key=lambda p: (p[1], p[0], p[2])))


def is_valid(packing: Packing, width_units: int, depth_units: int) -> bool:
    """True when every mat is inside the grid and no two mats share a cell."""
    if not packing:
        return False
    claimed = set()
    for x, y, orientation in packing:
        w_units, h_units = mat_size(orientation)
        if x < 0 or y < 0 or x + w_units > width_units or y + h_units > depth_units:
            return False
        for row in range(y, y + h_units):
            for col in range(x, x + w_units):
                if (col, row) in claimed:
                    return False
                claimed.add((col, row))
    return True


def occupied_cells(packing: Packing) -> set:
    """Every half-unit cell a packing covers."""
    cells = set()
    for x, y, orientation in packing:
        w_units, h_units = mat_size(orientation)
        for row in range(y, y + h_units):
            for col in range(x, x + w_units):
                cells.add((col, row))
    return cells


# --- Constructive candidate families ---------------------------------------


def band_layout(x_lo: int, x_hi: int, y_lo: int, y_hi: int, orientation: str) -> Packing:
    """Full rows of H mats (or full columns of V mats) inside a sub-rectangle."""
    mats = []
    if orientation == "H":
        y = y_lo
        while y + MAT_SHORT_UNITS <= y_hi:
            x = x_lo
            while x + MAT_LONG_UNITS <= x_hi:
                mats.append((x, y, "H"))
                x += MAT_LONG_UNITS
            y += MAT_SHORT_UNITS
    else:
        x = x_lo
        while x + MAT_SHORT_UNITS <= x_hi:
            y = y_lo
            while y + MAT_LONG_UNITS <= y_hi:
                mats.append((x, y, "V"))
                y += MAT_LONG_UNITS
            x += MAT_SHORT_UNITS
    return canonical(mats)


def pinwheel_layout(x0: int, y0: int) -> Packing:
    """Four mats meeting at a common corner, 180-degree symmetric about their block."""
    return canonical((
        (x0, y0, "H"),
        (x0, y0 + 2, "V"),
        (x0 + 4, y0, "V"),
        (x0 + 2, y0 + 4, "H"),
    ))


def pinwheel_anchors(width_units: int, depth_units: int) -> List[Tuple[int, int]]:
    """Block origins for the pinwheel family, centred first, then the corners."""
    if width_units < 6 or depth_units < 6:
        return []
    anchors = [((width_units - 6) // 2, (depth_units - 6) // 2)]
    for anchor in ((0, 0), (width_units - 6, 0), (0, depth_units - 6),
                   (width_units - 6, depth_units - 6)):
        if anchor not in anchors:
            anchors.append(anchor)
    return anchors


def fill_from_seed(seed: Packing, width_units: int, depth_units: int,
                   prefer: str, row_major: bool = True) -> Packing:
    """Place `seed` first, then tile the remaining free cells first-fit."""
    occupied = [[False] * width_units for _ in range(depth_units)]
    placed = list(seed)
    for x, y, orientation in seed:
        w_units, h_units = mat_size(orientation)
        for row in range(y, y + h_units):
            for col in range(x, x + w_units):
                occupied[row][col] = True
    other = "V" if prefer == "H" else "H"
    if row_major:
        cells = [(col, row) for row in range(depth_units) for col in range(width_units)]
    else:
        cells = [(col, row) for col in range(width_units) for row in range(depth_units)]
    for col, row in cells:
        if occupied[row][col]:
            continue
        for orientation in (prefer, other):
            w_units, h_units = mat_size(orientation)
            if col + w_units > width_units or row + h_units > depth_units:
                continue
            blocked = any(
                occupied[y][x]
                for y in range(row, row + h_units)
                for x in range(col, col + w_units)
            )
            if blocked:
                continue
            for y in range(row, row + h_units):
                for x in range(col, col + w_units):
                    occupied[y][x] = True
            placed.append((col, row, orientation))
            break
    return canonical(placed)


def generate_packings(room: Room) -> List[Packing]:
    """Every candidate packing the centred grid admits, in a fixed order."""
    width_units, depth_units = room.width_units, room.depth_units
    proposed: List[Packing] = []

    # 1. Full rows of H and full columns of V, aligned and offset by one unit.
    proposed.append(band_layout(0, width_units, 0, depth_units, "H"))
    proposed.append(band_layout(0, width_units, 1, depth_units, "H"))
    proposed.append(band_layout(0, width_units, 0, depth_units, "V"))
    proposed.append(band_layout(1, width_units, 0, depth_units, "V"))

    # 2. First-fit tilings, swept along the width or along the depth.
    for row_major in (True, False):
        for prefer in ("H", "V"):
            proposed.append(fill_from_seed((), width_units, depth_units, prefer, row_major))

    # 3. Pinwheel blocks: four mats meeting at a corner, then a first-fit refill.
    for anchor in pinwheel_anchors(width_units, depth_units):
        seed = pinwheel_layout(*anchor)
        for prefer in ("H", "V"):
            proposed.append(fill_from_seed(seed, width_units, depth_units, prefer, True))

    # 4. Mixed splits: one orientation on the left, the mirrored one on the right.
    for split in range(MAT_SHORT_UNITS, width_units - 1, MAT_SHORT_UNITS):
        for left, right in (("V", "H"), ("H", "V")):
            seed = (band_layout(0, split, 0, depth_units, left)
                    + band_layout(split, width_units, 0, depth_units, right))
            for prefer in ("H", "V"):
                proposed.append(
                    fill_from_seed(canonical(seed), width_units, depth_units, prefer, True))

    kept: List[Packing] = []
    seen = set()
    for packing in proposed:
        packing = canonical(packing)
        if packing in seen or not is_valid(packing, width_units, depth_units):
            continue
        seen.add(packing)
        kept.append(packing)
        if len(kept) >= MAX_CANDIDATES:
            break
    return kept


# --- Scoring ----------------------------------------------------------------


def wall_margins(room: Room, packing: Packing) -> Dict[str, Decimal]:
    """Real distance from each wall to the nearest mat, centring offset included."""
    min_x = min(x for x, _, _ in packing)
    max_x = max(x + mat_size(orientation)[0] for x, _, orientation in packing)
    min_y = min(y for _, y, _ in packing)
    max_y = max(y + mat_size(orientation)[1] for _, y, orientation in packing)
    return {
        "left": room.offset_x_m + UNIT_M * min_x,
        "right": room.offset_x_m + UNIT_M * (room.width_units - max_x),
        "top": room.offset_y_m + UNIT_M * min_y,
        "bottom": room.offset_y_m + UNIT_M * (room.depth_units - max_y),
    }


def symmetry_scores(room: Room, packing: Packing) -> Tuple[Fraction, Fraction]:
    """Fraction of mat area that mirrors onto mat area about each room centre axis.

    The sub-grid is centred, so mirroring a cell about the room centre is the same
    as mirroring it about the grid centre: column c -> width_units-1-c, row
    r -> depth_units-1-r.
    """
    covered = occupied_cells(packing)
    total = len(covered)
    if total == 0:
        return Fraction(0), Fraction(0)
    left_right = sum(
        1 for col, row in covered if (room.width_units - 1 - col, row) in covered)
    top_bottom = sum(
        1 for col, row in covered if (col, room.depth_units - 1 - row) in covered)
    return (Fraction(left_right, total), Fraction(top_bottom, total))


def margin_balance(margins_m: Dict[str, Decimal]) -> Fraction:
    """1.0 when all four wall margins are equal, falling away as they diverge."""
    values = list(margins_m.values())
    spread = max(values) - min(values)
    scale = max(UNIT_M, max(values))
    balance = Fraction(1) - Fraction(spread) / Fraction(scale)
    return balance if balance > 0 else Fraction(0)


def label_mats(packing: Packing) -> Tuple[Mat, ...]:
    """Number H1..Hn and V1..Vn in reading order (smallest y, then smallest x)."""
    counters = {"H": 0, "V": 0}
    mats = []
    for x, y, orientation in canonical(packing):
        counters[orientation] += 1
        mats.append(Mat(x, y, orientation, "{}{}".format(orientation, counters[orientation])))
    return tuple(mats)


def build_arrangement(room: Room, ident: str, packing: Packing) -> Arrangement:
    """Turn a valid packing into a scored Arrangement."""
    mats = label_mats(packing)
    covered_cells = sum(mat.w_units * mat.h_units for mat in mats)
    covered_m2 = CELL_AREA_M2 * covered_cells
    uncovered_m2 = room.room_area_m2 - covered_m2
    margins = wall_margins(room, packing)
    symmetry_lr, symmetry_tb = symmetry_scores(room, packing)
    coverage = Fraction(covered_m2) / Fraction(room.room_area_m2)
    balance = margin_balance(margins)
    score = (Fraction(1, 2) * coverage
             + Fraction(3, 10) * (symmetry_lr + symmetry_tb) / 2
             + Fraction(1, 5) * balance)
    return Arrangement(
        ident=ident,
        mats=mats,
        margins_m=margins,
        symmetry_lr=symmetry_lr,
        symmetry_tb=symmetry_tb,
        grid_cells=room.width_units * room.depth_units,
        covered_cells=covered_cells,
        covered_m2=covered_m2,
        uncovered_m2=uncovered_m2,
        coverage=coverage,
        margin_balance=balance,
        score=score,
    )


def candidates(room: Room) -> List[Arrangement]:
    """Every valid candidate for a room, in generation order."""
    return [
        build_arrangement(room, "A{}".format(index + 1), packing)
        for index, packing in enumerate(generate_packings(room))
    ]


# --- Ranking ----------------------------------------------------------------


def notes_for(ordered: Sequence[Arrangement]) -> List[str]:
    """One plain-English line per arrangement, best first."""
    full_count = sum(1 for arr in ordered if arr.full_coverage)
    notes = []
    for arr in ordered:
        mirrors = arr.symmetry_lr == 1 and arr.symmetry_tb == 1
        if arr.full_coverage and full_count == 1:
            note = "only option filling the whole usable grid"
        elif arr.full_coverage and arr.v_count == 0:
            note = "fills the grid with H mats only"
        elif arr.full_coverage and arr.h_count == 0:
            note = "fills the grid with V mats only"
        elif arr.full_coverage:
            note = "fills the grid with a mixed H/V weave"
        elif mirrors:
            note = "mirror-symmetric about both room axes"
        elif arr.symmetry_lr == 1:
            note = "mirror-symmetric left-to-right"
        elif arr.symmetry_tb == 1:
            note = "mirror-symmetric top-to-bottom"
        else:
            note = "{} m2 of floor left bare at the walls".format(format_m2(arr.uncovered_m2))
        notes.append(note)
    return notes


def ranking_key(arrangement: Arrangement) -> tuple:
    """Total order: score down, uncovered area up, H mats down, first label up."""
    return (-arrangement.score, arrangement.uncovered_m2,
            -arrangement.h_count, arrangement.mats[0].label)


def rank(room: Room) -> List[Arrangement]:
    """Score every candidate and return them best first, notes attached."""
    ordered = sorted(candidates(room), key=ranking_key)
    return [replace(arr, note=note) for arr, note in zip(ordered, notes_for(ordered))]


# --- Rendering --------------------------------------------------------------


def diagram_lines(room: Room, arrangement: Arrangement) -> List[str]:
    """A wall-framed ASCII plan: each half-unit is two characters wide, one tall."""
    width = room.width_units * 2
    canvas = [[" "] * width for _ in range(room.depth_units)]
    for mat in arrangement.mats:
        for row in range(mat.y, mat.y + mat.h_units):
            for col in range(mat.x, mat.x + mat.w_units):
                canvas[row][col * 2] = "."
                canvas[row][col * 2 + 1] = "."
    for mat in arrangement.mats:
        for offset, character in enumerate(mat.label):
            col = mat.x * 2 + offset
            if col < (mat.x + mat.w_units) * 2:
                canvas[mat.y][col] = character
    edge = "+" + "-" * width + "+"
    lines = [edge]
    lines.extend("|" + "".join(row) + "|" for row in canvas)
    lines.append(edge)
    return lines


def summary_lines(room: Room, arrangement: Arrangement) -> List[str]:
    """Five lines of numbers: room, margins, mats, symmetry, weights."""
    margins = arrangement.margins_m
    return [
        "Room: {} m x {} m -> usable grid {} x {} half-units ({} m x {} m)".format(
            format_m(room.width_m), format_m(room.depth_m),
            room.width_units, room.depth_units,
            format_m(room.usable_width_m), format_m(room.usable_depth_m)),
        "Margins: left {} m  right {} m  top {} m  bottom {} m".format(
            format_m(margins["left"]), format_m(margins["right"]),
            format_m(margins["top"]), format_m(margins["bottom"])),
        "Mats: {} ({}) covering {} m2  |  uncovered {} m2 of {} m2".format(
            len(arrangement.mats), arrangement.mix_label,
            format_m2(arrangement.covered_m2), format_m2(arrangement.uncovered_m2),
            format_m2(room.room_area_m2)),
        "Symmetry: left-right {}  top-bottom {}  |  score {}".format(
            format_score(arrangement.symmetry_lr),
            format_score(arrangement.symmetry_tb),
            format_score(arrangement.score)),
        WEIGHTS_LINE,
    ]


def shortlist_lines(room: Room, ranked: Sequence[Arrangement]) -> List[str]:
    """The ranked alternatives table, at most three rows, best first."""
    if len(ranked) == 1:
        return ["Ranked options: No other arrangement fits this room.", WEIGHTS_LINE]
    lines = ["Ranked options (best first)",
             "   #  score  mats     sym     open  note"]
    for position, arr in enumerate(ranked[:SHORTLIST_SIZE], start=1):
        lines.append("{:>4}  {:>5}  {:<7}  {:>4}  {:>6}  {}".format(
            position, format_score(arr.score), arr.mix_label,
            format_score(arr.symmetry), format_m2(arr.uncovered_m2) + "m2", arr.note))
    lines.append(WEIGHTS_LINE)
    return lines


def render(room: Room, ranked: Sequence[Arrangement], out=None) -> None:
    """Print the plan page: diagram, legend, summary, then the shortlist."""
    if out is None:
        out = sys.stdout
    for line in diagram_lines(room, ranked[0]):
        out.write(line + "\n")
    out.write(LEGEND + "\n")
    for line in summary_lines(room, ranked[0]):
        out.write(line + "\n")
    out.write("\n")
    for line in shortlist_lines(room, ranked):
        out.write(line + "\n")


# --- Room input -------------------------------------------------------------

BANNER = (
    "TatamiFit {} -- tatami mat layout planner (0.455 m half-unit grid)\n"
    "Plan whole {} m x {} m tatami in a rectangular room, measured in metres.\n"
    "Usage: python3 tatamifit.py   (answer the width, then the depth; Enter plans)\n"
).format(VERSION, format_m(MAT_SHORT_M), format_m(MAT_LONG_M))


def is_tty(stream) -> bool:
    """True only for a real terminal; False for pipes, files and /dev/null."""
    probe = getattr(stream, "isatty", None)
    return bool(probe and probe())


def wait_for_input(instream, timeout: float) -> bool:
    """True when stdin is ready, or is not an interactive terminal at all."""
    if not is_tty(instream) or not hasattr(select, "select"):
        return True
    try:
        ready, _, _ = select.select([instream], [], [], timeout)
    except (ValueError, OSError):
        return True
    return bool(ready)


def read_line(instream, first: bool = False) -> str:
    """Read one input line; the very first prompt gives up when idle."""
    if first and not wait_for_input(instream, FIRST_ANSWER_TIMEOUT_S):
        raise PromptIdle()
    line = instream.readline()
    if line == "":
        raise PlanAborted()
    return line


def end_prompt(instream, out) -> None:
    """Terminate the prompt line when stdin is piped (nothing echoes the Enter)."""
    if not is_tty(instream):
        out.write("\n")


def write_prompt(out, text: str) -> None:
    out.write(text)
    out.flush()


def parse_metres(text: str) -> Decimal:
    """Parse one positive number of metres, or explain why it is not one."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError("'{}' is not a number of metres".format(text))
    if not value.is_finite():
        raise ValueError("'{}' is not a number of metres".format(text))
    if value <= 0:
        raise ValueError("enter a positive number of metres")
    return value


def ask_dimension(name: str, hint: str, example: str, key: str,
                  accepted: Dict[str, Decimal], instream, out,
                  first: bool = False) -> Decimal:
    """Ask for one dimension until it is accepted; a bare Enter keeps a retained value."""
    while True:
        retained = accepted.get(key)
        if retained is None:
            prompt = "{} (m) {}, e.g. {}: ".format(name, hint, example)
        else:
            prompt = "{} (m) [{}]: ".format(name, format_m(retained))
        write_prompt(out, prompt)
        line = read_line(instream, first=first)
        end_prompt(instream, out)
        text = line.strip()
        if not text:
            if retained is not None:
                return retained
            out.write("Try again: enter a number of metres, e.g. {}\n".format(example))
            continue
        try:
            value = parse_metres(text)
        except ValueError as exc:
            out.write("Try again: {}\n".format(exc))
            continue
        accepted[key] = value
        return value


def ask_confirm(instream, out) -> str:
    """Enter plans the room, w re-asks the width, d re-asks the depth."""
    while True:
        write_prompt(out, "Plan this room? [Enter=plan, w=width, d=depth]: ")
        line = read_line(instream)
        end_prompt(instream, out)
        answer = line.strip().lower()
        if answer in ("", "y", "yes", "plan"):
            return "plan"
        if answer in ("w", "width"):
            return "width"
        if answer in ("d", "depth"):
            return "depth"
        out.write("Try again: press Enter to plan, w for width or d for depth\n")


def read_room(instream, out) -> Room:
    """Collect the room: width then depth, then a confirm step over retained answers."""
    accepted: Dict[str, Decimal] = {}
    ask_width = ask_depth = True
    while True:
        if ask_width:
            accepted["width"] = ask_dimension(
                "Width", WIDTH_HINT, WIDTH_EXAMPLE, "width", accepted, instream, out,
                first=not accepted)
        if ask_depth:
            accepted["depth"] = ask_dimension(
                "Depth", DEPTH_HINT, DEPTH_EXAMPLE, "depth", accepted, instream, out)
        room = quantise(accepted["width"], accepted["depth"])
        out.write(preview_line(room) + "\n")
        out.flush()
        action = ask_confirm(instream, out)
        if action == "plan":
            return room
        ask_width = action == "width"
        ask_depth = action == "depth"

HELP_TEXT = """TatamiFit {version} -- plan whole-mat tatami layouts for a rectangular room.

Usage:
  python3 tatamifit.py                  answer two prompts (width, then depth)
  printf '3.64\\n2.73\\n\\n' | python3 tatamifit.py
  python3 tatamifit.py --help
  python3 tatamifit.py --version

Input:
  Width (m) then Depth (m), each a positive number of metres on its own line.
  After both answers the room is snapped to the 0.455 m half-unit grid and
  shown with the gap left at each wall. Enter at the confirm line plans the
  room; w or d re-asks one dimension, where a bare Enter keeps the value in
  brackets.
  On a terminal with nothing typed for {timeout:.0f} seconds the usage summary
  is printed and TatamiFit exits instead of waiting forever.

Output:
  A wall-framed ASCII plan ({legend}),
  a summary block with the wall margins, symmetry and uncovered area, then a
  ranked shortlist of up to three arrangements with the scoring weights.

Limits:
  at least one {mat_short} m x {mat_long} m tatami must fit (e.g. 1.82 x 1.82 m)
  drawing range: {max_wu} x {max_du} half-units, i.e. {max_w} x {max_d} m

Exit status:
  0  a plan was printed
  1  no plan produced (Ctrl-D or Ctrl-C at a prompt)
  2  the room was refused (too small, or outside the drawing range)

Examples:
  printf '3.70\\n2.90\\n\\n' | python3 tatamifit.py
  python3 tatamifit.py          # then type a width, a depth, Enter twice
""".format(version=VERSION, legend=LEGEND, mat_short=format_m(MAT_SHORT_M),
           mat_long=format_m(MAT_LONG_M), max_wu=MAX_WIDTH_UNITS, max_du=MAX_DEPTH_UNITS,
           max_w=format_m(MAX_WIDTH_M), max_d=format_m(MAX_DEPTH_M),
           timeout=FIRST_ANSWER_TIMEOUT_S)


def run_session(argv=None) -> int:
    """Run one session: banner, room input, plan, render, and the exit contract."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        first = arguments[0]
        if first in ("-h", "--help"):
            sys.stdout.write(HELP_TEXT)
            return 0
        if first in ("-V", "--version"):
            sys.stdout.write("TatamiFit {}\n".format(VERSION))
            return 0
        sys.stderr.write("tatamifit: unknown option {!r}\n".format(first))
        sys.stderr.write("Try 'python3 tatamifit.py --help' for usage.\n")
        return 2
    out = sys.stdout
    out.write(BANNER)
    out.flush()
    try:
        room = read_room(sys.stdin, out)
    except PromptIdle:
        out.write(
            "No answer after {:.0f} seconds -- showing the usage summary.\n"
            "Run 'sh demo.sh' for a recorded non-interactive demo.\n".format(
                FIRST_ANSWER_TIMEOUT_S))
        out.write(HELP_TEXT)
        out.flush()
        return 0
    except PlanAborted:
        out.write("\n")
        out.flush()
        sys.stderr.write("no plan produced\n")
        return 1
    except KeyboardInterrupt:
        out.write("\n")
        out.flush()
        sys.stderr.write("no plan produced\n")
        return 1
    except RoomRefused as refused:
        out.write("{}\n".format(refused))
        out.flush()
        return 2
    render(room, rank(room), out)
    return 0


def main(argv=None) -> int:
    """Entry point for tatamifit.py, cli.py and the installed console script."""
    try:
        status = run_session(argv)
        sys.stdout.flush()
        return status
    except BrokenPipeError:
        # a reader such as `head` closed the pipe: leave without a traceback
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 1


if __name__ == "__main__":
    try:
        status = main()
        sys.stdout.flush()
        sys.exit(status)
    except KeyboardInterrupt:
        sys.stderr.write("no plan produced\n")
        sys.exit(1)
    except BrokenPipeError:
        # a reader such as `head` closed the pipe: leave without a traceback
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
