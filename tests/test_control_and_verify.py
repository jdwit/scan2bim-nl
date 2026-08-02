from __future__ import annotations

import math

import pytest

from scan2bim import control as control_mod
from scan2bim import verify as verify_mod


def codes(findings):
    return {f.code for f in findings}


def test_valid_control_file_passes(control_yaml):
    control = control_mod.load(control_yaml)
    findings = control_mod.validate(control)
    assert control_mod.worst(findings) in {"ok", "warn"}
    assert "fail" not in {f.severity for f in findings}


def test_missing_diagonal_is_flagged(control_yaml):
    control = control_mod.load(control_yaml)
    control.rooms[0].diagonal_a_mm = None
    control.rooms[0].diagonal_b_mm = None
    assert "no-diagonal" in codes(control_mod.validate(control))


def test_out_of_square_room_is_reported(control_yaml):
    control = control_mod.load(control_yaml)
    # 3000 x 4000 has a true diagonal of 5000; 5120 is 120 mm out.
    control.rooms[0].diagonal_a_mm = 5120
    found = codes(control_mod.validate(control))
    assert "out-of-square" in found
    assert "diagonals-differ" in found


def test_impossible_storey_height_fails(control_yaml):
    control = control_mod.load(control_yaml)
    control.storey_heights[0].floor_to_floor_mm = 3000  # below floor-to-ceiling of 3120
    findings = control_mod.validate(control)
    assert "impossible-height" in codes(findings)
    assert control_mod.worst(findings) == "fail"


def test_wall_thickness_in_centimetres_fails(control_yaml):
    control = control_mod.load(control_yaml)
    control.walls[0].thickness_mm = 32  # someone typed centimetres
    assert "implausible-thickness" in codes(control_mod.validate(control))


def test_duplicate_ids_fail(control_yaml):
    control = control_mod.load(control_yaml)
    control.control_distances[1].id = control.control_distances[0].id
    assert "duplicate-id" in codes(control_mod.validate(control))


def test_too_few_control_distances_warns(control_yaml):
    control = control_mod.load(control_yaml)
    control.control_distances = control.control_distances[:2]
    assert "few-control-distances" in codes(control_mod.validate(control))


def test_expected_diagonal():
    assert control_mod.expected_diagonal_mm(3000, 4000) == pytest.approx(5000)


def test_invalid_yaml_raises(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("rooms: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a valid control file"):
        control_mod.load(path)


def _picked(tmp_path, rows: str, name: str = "picked.csv"):
    path = tmp_path / name
    path.write_text(rows, encoding="utf-8")
    return path


def test_read_markers_converts_units(tmp_path):
    path = _picked(tmp_path, "A,0,0,0\nB,12.0,0,0\n")
    markers = verify_mod.read_markers(path, units="m")
    assert markers["B"].x_mm == pytest.approx(12000)


def test_read_markers_skips_header(tmp_path):
    path = _picked(tmp_path, "name,x,y,z\nA,0,0,0\nB,1,0,0\n")
    assert set(verify_mod.read_markers(path, units="m")) == {"A", "B"}


def test_read_markers_rejects_empty(tmp_path):
    path = _picked(tmp_path, "nothing useful\n")
    with pytest.raises(ValueError, match="No marker rows"):
        verify_mod.read_markers(path)


def test_read_markers_rejects_unknown_units(tmp_path):
    path = _picked(tmp_path, "A,0,0,0\n")
    with pytest.raises(ValueError, match="Unknown units"):
        verify_mod.read_markers(path, units="furlong")


def test_compare_passes_within_tolerance(control_yaml, tmp_path):
    control = control_mod.load(control_yaml)
    # Place markers so cloud distances land within a few millimetres of the measured values.
    path = _picked(
        tmp_path,
        "A,0,0,0\nB,12.004,0,0\nC,0,8.002,0\nD,15.001,0,0\n",
    )
    markers = verify_mod.read_markers(path, units="m")
    result = verify_mod.compare(control, markers)
    assert result.passed
    assert result.scale_factor == pytest.approx(1.0, abs=0.005)
    assert result.max_abs_deviation_pct < 0.2


def test_compare_fails_when_cloud_is_stretched(control_yaml, tmp_path):
    control = control_mod.load(control_yaml)
    path = _picked(tmp_path, "A,0,0,0\nB,12.6,0,0\nC,0,8.4,0\nD,15.75,0,0\n")
    markers = verify_mod.read_markers(path, units="m")
    result = verify_mod.compare(control, markers)
    assert not result.passed
    assert result.max_abs_deviation_pct == pytest.approx(5.0, abs=0.2)
    assert "exceeds" in result.advice


def test_systematic_scale_error_is_advised(control_yaml, tmp_path):
    control = control_mod.load(control_yaml)
    # Every distance 0.5 percent long: inside a 1 percent tolerance, but systematic.
    path = _picked(tmp_path, "A,0,0,0\nB,12.06,0,0\nC,0,8.04,0\nD,15.075,0,0\n")
    markers = verify_mod.read_markers(path, units="m")
    result = verify_mod.compare(control, markers)
    assert result.passed
    assert result.scale_factor == pytest.approx(1 / 1.005, abs=0.001)
    assert "systematically off" in result.advice


def test_missing_marker_blocks_pass(control_yaml, tmp_path):
    control = control_mod.load(control_yaml)
    path = _picked(tmp_path, "A,0,0,0\nB,12.0,0,0\n")
    markers = verify_mod.read_markers(path, units="m")
    result = verify_mod.compare(control, markers)
    assert not result.passed
    assert "C" in result.advice and "D" in result.advice


def test_empty_comparison_is_not_a_pass():
    result = verify_mod.Verification(comparisons=[], missing_markers=[], tolerance_pct=1.0)
    assert not result.passed
    assert math.isnan(result.rms_deviation_mm)
    assert "Nothing to compare" in result.advice


def test_unquoted_yaml_date_is_accepted(tmp_path):
    path = tmp_path / "control.yaml"
    path.write_text("project: x\nsurveyed_on: 2026-11-03\n", encoding="utf-8")
    assert control_mod.load(path).surveyed_on == "2026-11-03"
