"""Printable markers.

The weak link between the tape measure and the point cloud is recognition: a taped sheet of
paper looks like every other taped sheet of paper once it is a few thousand points. These
sheets carry a large label and a high contrast quadrant pattern, so the same physical point can
be named on site, found back in the cloud, and picked with confidence.
"""

from __future__ import annotations

from pathlib import Path

from scan2bim.control import ControlFile

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Markers - {project}</title>
<style>
  @page {{ size: A4 portrait; margin: 10mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Helvetica, Arial, sans-serif; margin: 0; }}
  .sheet {{
    width: 190mm; height: 277mm; page-break-after: always;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
  }}
  .pattern {{
    width: 160mm; height: 160mm; display: grid;
    grid-template: 1fr 1fr / 1fr 1fr; border: 4mm solid #000;
  }}
  .pattern div:nth-child(1), .pattern div:nth-child(4) {{ background: #000; }}
  .pattern div:nth-child(2), .pattern div:nth-child(3) {{ background: #fff; }}
  .label {{ font-size: 90mm; font-weight: bold; line-height: 1; margin: 6mm 0; }}
  .meta {{ font-size: 5mm; color: #333; text-align: center; }}
  .crosshair {{ position: relative; }}
  .crosshair::after {{
    content: ""; position: absolute; left: 50%; top: 50%;
    width: 30mm; height: 30mm; transform: translate(-50%, -50%);
    border: 1mm solid #c00; border-radius: 50%;
  }}
</style>
</head>
<body>
{sheets}</body>
</html>
"""

SHEET_TEMPLATE = """<section class="sheet">
  <div class="pattern crosshair"><div></div><div></div><div></div><div></div></div>
  <div class="label">{name}</div>
  <div class="meta">{project} &middot; marker {name} &middot;
    tape the red circle over the point you measure from</div>
</section>
"""


def names_from_control(control: ControlFile) -> list[str]:
    """Every marker referenced by a control distance, in first-seen order."""
    seen: list[str] = []
    for distance in control.control_distances:
        for name in (distance.from_marker, distance.to_marker):
            if name not in seen:
                seen.append(name)
    return seen


def render(project: str, names: list[str]) -> str:
    if not names:
        raise ValueError(
            "No marker names. Add control_distances to the control file, or pass names explicitly."
        )
    sheets = "".join(SHEET_TEMPLATE.format(name=name, project=project) for name in names)
    return PAGE_TEMPLATE.format(project=project, sheets=sheets)


def write(content: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
