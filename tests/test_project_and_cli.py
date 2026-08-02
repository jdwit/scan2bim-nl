from __future__ import annotations

import pytest
from typer.testing import CliRunner

from scan2bim import config
from scan2bim.cli import app

runner = CliRunner()


def test_project_roundtrip(tmp_path):
    root = tmp_path / "house"
    root.mkdir()
    config.create_layout(root)
    project = config.Project(name="house", rd_x=139657.02, rd_y=471121.55, radius_m=50)
    config.save(root, project)

    found_root, loaded = config.load(root / "raw")  # walks up from a subdirectory
    assert found_root == root
    assert loaded.name == "house"
    assert loaded.bbox() == (139607.02, 471071.55, 139707.02, 471171.55)
    assert loaded.bbox(10)[0] == pytest.approx(139647.02)


def test_bbox_without_location_raises():
    with pytest.raises(ValueError, match="no coordinates"):
        config.Project(name="x").bbox()


def test_load_without_project_file(tmp_path):
    with pytest.raises(FileNotFoundError, match=r"project\.toml"):
        config.load(tmp_path)


def test_cli_init_creates_layout_and_templates(tmp_path):
    result = runner.invoke(app, ["project", "init", "house", "--directory", str(tmp_path / "h")])
    assert result.exit_code == 0, result.output
    root = tmp_path / "h"
    assert (root / "project.toml").is_file()
    assert (root / "control" / "control.yaml").is_file()
    assert (root / "docs" / "checklist.md").is_file()
    for folder in config.LAYOUT:
        assert (root / folder).is_dir()
    assert "CHANGE-ME" not in (root / "control" / "control.yaml").read_text()


def test_cli_init_refuses_to_overwrite(tmp_path):
    target = tmp_path / "h"
    runner.invoke(app, ["project", "init", "house", "--directory", str(target)])
    result = runner.invoke(app, ["project", "init", "house", "--directory", str(target)])
    assert result.exit_code == 1


def test_cli_validate_flags_the_untouched_template(tmp_path, monkeypatch):
    root = tmp_path / "h"
    runner.invoke(app, ["project", "init", "house", "--directory", str(root)])
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["control", "validate"])
    # The template ships with zeros, which must not silently pass.
    assert result.exit_code == 1


def test_cli_reports_missing_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["project", "show"])
    assert result.exit_code == 1
    assert "project.toml" in result.output


def test_cli_report_without_control(tmp_path, monkeypatch):
    root = tmp_path / "h"
    runner.invoke(app, ["project", "init", "house", "--directory", str(root)])
    (root / "control" / "control.yaml").unlink()
    monkeypatch.chdir(root)
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
    content = (root / "reports" / "provenance.md").read_text()
    assert "unverified" in content
    assert "No raw files yet" in content
