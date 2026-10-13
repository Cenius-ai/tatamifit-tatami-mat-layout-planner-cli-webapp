"""F5 / T6: the ASCII plan page, the legend, the summary and the shortlist."""

from decimal import Decimal

from tatamifit import (LEGEND, MAX_DIAGRAM_ROWS, MAX_LINE_WIDTH, diagram_lines,
                       format_m2, quantise, rank, shortlist_lines, summary_lines)


def plan(width, depth):
    snapped = quantise(Decimal(width), Decimal(depth))
    return snapped, rank(snapped)


def test_legend_line_is_exactly_the_documented_text():
    assert LEGEND == "H = long-along-width, V = long-along-depth"
    _, ranked = plan("3.64", "2.73")
    assert diagram_lines(quantise(Decimal("3.64"), Decimal("2.73")), ranked[0])


def test_labels_carry_their_orientation_and_reading_order():
    snapped, ranked = plan("3.64", "2.73")
    best = ranked[0]
    labels = [mat.label for mat in best.mats]
    assert labels == [mat.label for mat in sorted(best.mats, key=lambda m: (m.y, m.x))]
    for mat in best.mats:
        assert mat.label.startswith(mat.orientation)
    h_labels = [m.label for m in best.mats if m.orientation == "H"]
    assert h_labels == ["H{}".format(i) for i in range(1, len(h_labels) + 1)]
    assert len(h_labels) == 6


def test_every_mat_label_is_drawn_inside_the_diagram():
    snapped, ranked = plan("3.70", "2.90")
    diagram = "\n".join(diagram_lines(snapped, ranked[0]))
    for mat in ranked[0].mats:
        assert mat.label in diagram


def test_labels_are_inside_their_own_mat():
    snapped, ranked = plan("3.70", "2.90")
    body = diagram_lines(snapped, ranked[0])[1:-1]
    for mat in ranked[0].mats:
        row = body[mat.y]
        start = 1 + mat.x * 2
        assert row[start:start + len(mat.label)] == mat.label


def test_widest_room_stays_inside_the_page_budget():
    snapped, ranked = plan("17.745", "7.28")
    diagram = diagram_lines(snapped, ranked[0])
    summary = summary_lines(snapped, ranked[0])
    assert len(diagram) <= MAX_DIAGRAM_ROWS
    assert len(diagram) + 1 + len(summary) <= 24
    for line in diagram + [LEGEND] + summary + shortlist_lines(snapped, ranked):
        assert len(line) <= MAX_LINE_WIDTH


def test_summary_reports_the_documented_numbers():
    snapped, ranked = plan("3.70", "2.90")
    best = ranked[0]
    assert format_m2(best.covered_m2) == "9.94"
    assert format_m2(best.uncovered_m2) == "0.79"
    summary = "\n".join(summary_lines(snapped, best))
    assert "Mats: 6 (6H+0V) covering 9.94 m2  |  uncovered 0.79 m2 of 10.73 m2" in summary
    assert "Margins: left 0.03 m  right 0.03 m  top 0.085 m  bottom 0.085 m" in summary
    assert "Symmetry: left-right 1.00  top-bottom 1.00" in summary
    assert "Weights: coverage 0.50, symmetry 0.30, margin balance 0.20" in summary


def test_margins_come_from_the_real_walls_not_the_grid_edge():
    snapped, ranked = plan("1.00", "1.90")
    margins = ranked[0].margins_m
    assert margins["left"] == Decimal("0.045") and margins["right"] == Decimal("0.045")
    assert margins["top"] == Decimal("0.04") and margins["bottom"] == Decimal("0.04")


def test_summary_reports_the_bare_wall_when_a_grid_row_is_empty():
    snapped, ranked = plan("1.82", "1.82")
    empty_row = [a for a in ranked if not a.full_coverage]
    assert empty_row, "expected at least one candidate that leaves a wall bare"
    assert empty_row[0].margins_m["bottom"] > empty_row[0].margins_m["left"]


def test_shortlist_is_capped_at_three_rows_with_notes():
    snapped, ranked = plan("3.70", "2.90")
    rows = shortlist_lines(snapped, ranked)
    assert rows[0] == "Ranked options (best first)"
    assert len(rows) == 1 + 1 + 3 + 1
    for row in rows[2:5]:
        assert row.split()[0] in ("1", "2", "3")
        assert row.strip().endswith(ranked[int(row.split()[0]) - 1].note)


def test_single_candidate_room_says_so():
    snapped, ranked = plan("1.00", "1.90")
    rows = shortlist_lines(snapped, ranked)
    assert rows[0] == "Ranked options: No other arrangement fits this room."
