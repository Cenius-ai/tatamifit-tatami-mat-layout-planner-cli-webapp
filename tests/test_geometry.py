"""F2 / T3: the room entity, centred half-unit quantisation and the refusals."""

from decimal import Decimal

import pytest

from tatamifit import (MAX_DEPTH_M, MAX_WIDTH_M, RoomRefused, fits_one_mat,
                       preview_line, quantise)


def room(width, depth):
    return quantise(Decimal(width), Decimal(depth))


def test_centred_grid_for_3_70_by_2_90():
    snapped = room("3.70", "2.90")
    assert (snapped.width_units, snapped.depth_units) == (8, 6)
    assert snapped.offset_x_m == Decimal("0.03")
    assert snapped.offset_y_m == Decimal("0.085")
    preview = preview_line(snapped)
    assert "usable grid 8 x 6 half-units (3.64 m x 2.73 m)" in preview
    assert "0.03 m to each side wall, 0.085 m to each end wall" in preview


def test_exact_multiple_leaves_no_remainder():
    snapped = room("3.64", "2.73")
    assert (snapped.width_units, snapped.depth_units) == (8, 6)
    assert snapped.offset_x_m == 0
    assert snapped.offset_y_m == 0
    assert "0.00 m to each side wall, 0.00 m to each end wall" in preview_line(snapped)


def test_axes_are_floored_not_rounded():
    assert room("3.6", "2.7").width_units == 7   # 7.91 half-units
    assert room("3.6", "2.7").depth_units == 5   # 5.93 half-units
    assert room("3.64", "2.73").usable_width_m == Decimal("3.640")


@pytest.mark.parametrize("width,depth", [("1.20", "0.80"), ("0.50", "0.50"), ("2.00", "0.30")])
def test_rooms_too_small_for_one_mat_are_refused(width, depth):
    with pytest.raises(RoomRefused) as excinfo:
        room(width, depth)
    assert "too small for a single 0.91 m x 1.82 m tatami" in str(excinfo.value)


def test_room_outside_the_drawing_range_is_refused():
    with pytest.raises(RoomRefused) as excinfo:
        room("20.00", "20.00")
    message = str(excinfo.value)
    assert "39 x 16" in message
    assert "17.745" in message and "7.28" in message


@pytest.mark.parametrize("width,depth", [("17.75", "7.28"), ("17.745", "7.29")])
def test_rooms_just_over_the_range_are_refused(width, depth):
    with pytest.raises(RoomRefused):
        room(width, depth)


def test_boundary_rooms_are_accepted():
    assert room("0.91", "1.82").width_units == 2
    widest = room("17.745", "7.28")
    assert (widest.width_units, widest.depth_units) == (39, 16)
    assert widest.usable_width_m == MAX_WIDTH_M and widest.usable_depth_m == MAX_DEPTH_M


def test_single_mat_shapes():
    assert fits_one_mat(4, 2) and fits_one_mat(2, 4)
    assert not fits_one_mat(4, 1) and not fits_one_mat(1, 4) and not fits_one_mat(3, 3)
