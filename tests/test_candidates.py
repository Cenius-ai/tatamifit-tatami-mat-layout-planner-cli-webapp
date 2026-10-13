"""F3 / F4: candidate generation, validity, determinism and mirror scoring."""

from decimal import Decimal

from tatamifit import (build_arrangement, candidates, generate_packings,
                       mat_size, quantise, rank)


def room(width, depth):
    return quantise(Decimal(width), Decimal(depth))


def cells_of(arrangement):
    cells = set()
    for mat in arrangement.mats:
        width, height = mat_size(mat.orientation)
        assert (width, height) == ((4, 2) if mat.orientation == "H" else (2, 4))
        for row in range(mat.y, mat.y + height):
            for col in range(mat.x, mat.x + width):
                assert (col, row) not in cells, "two mats share a cell"
                cells.add((col, row))
    return cells


def test_every_candidate_stays_inside_the_grid_without_overlap():
    snapped = room("3.70", "2.90")
    found = candidates(snapped)
    assert found
    for arrangement in found:
        cells = cells_of(arrangement)
        assert len(cells) == arrangement.covered_cells
        for mat in arrangement.mats:
            assert 0 <= mat.x and mat.x + mat.w_units <= snapped.width_units
            assert 0 <= mat.y and mat.y + mat.h_units <= snapped.depth_units
    assert rank(snapped)[0].full_coverage


def test_generation_is_deterministic():
    snapped = room("3.70", "2.90")
    assert generate_packings(snapped) == generate_packings(snapped)
    assert [a.ident for a in candidates(snapped)] == [a.ident for a in candidates(snapped)]


def test_best_candidate_covers_the_whole_usable_grid():
    snapped = room("3.64", "2.73")
    best = rank(snapped)[0]
    assert best.covered_cells == snapped.width_units * snapped.depth_units


def test_mirror_symmetric_candidate_outranks_equal_coverage():
    snapped = room("3.70", "2.90")
    centred = build_arrangement(snapped, "MID", ((0, 2, "H"), (4, 2, "H")))
    off_edge = build_arrangement(snapped, "EDGE", ((0, 0, "H"), (4, 0, "H")))
    assert centred.covered_cells == off_edge.covered_cells
    assert centred.symmetry_lr == 1 and centred.symmetry_tb == 1
    assert off_edge.symmetry_tb < 1
    assert centred.score > off_edge.score


def test_four_by_four_grid_holds_exactly_two_mats():
    snapped = room("1.82", "1.82")
    assert (snapped.width_units, snapped.depth_units) == (4, 4)
    ranked = rank(snapped)
    assert ranked[0].full_coverage
    assert len(ranked[0].mats) == 2
    assert all(len(a.mats) == 2 for a in ranked if a.full_coverage)


def test_mixed_symmetric_candidate_reaches_the_shortlist():
    snapped = room("3.64", "1.82")
    ranked = rank(snapped)
    mixed = [a for a in ranked[:3] if a.mixed]
    assert mixed, [a.mix_label for a in ranked[:3]]
    assert mixed[0].full_coverage
    assert mixed[0].symmetry_lr == 1 and mixed[0].symmetry_tb == 1


def test_room_that_only_admits_one_candidate():
    snapped = room("1.00", "1.90")
    assert len(candidates(snapped)) == 1
    assert rank(snapped)[0].mix_label == "0H+1V"


def test_ranking_follows_the_documented_total_order():
    ranked = rank(room("3.70", "2.90"))
    order = [(-a.score, a.uncovered_m2, -a.h_count, a.mats[0].label) for a in ranked]
    assert order == sorted(order)
