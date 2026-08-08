"""Provenance report: what was measured, from which sources, and how far off the cloud was.

The point is auditability. A model that claims to be as-built should carry the evidence with
it: which open datasets were pulled and when, which control measurements were taken, and the
deviation between the cloud and those measurements.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from scan2bim.config import Project
from scan2bim.control import ControlFile, Finding, worst
from scan2bim.verify import Verification

DIGEST_CHUNK = 1 << 20


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(DIGEST_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def build(
    project: Project,
    root: Path,
    *,
    control: ControlFile | None = None,
    findings: list[Finding] | None = None,
    verification: Verification | None = None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# As-built provenance report - {project.name}",
        "",
        f"Generated {now} by scan2bim-nl.",
        "",
        "## Project",
        "",
        f"- Address: {project.address or 'not set'}",
    ]
    if project.has_location:
        lines.append(f"- RD coordinates: {project.rd_x:.2f}, {project.rd_y:.2f} (EPSG:28992)")
        xmin, ymin, xmax, ymax = project.bbox()
        lines.append(f"- Area of interest: {xmin:.0f},{ymin:.0f} to {xmax:.0f},{ymax:.0f}")
    if project.bag_object_id:
        lines.append(f"- BAG object id: {project.bag_object_id}")

    lines += ["", "## Retrieved data", ""]
    raw_files = sorted(p for p in (root / "raw").rglob("*") if p.is_file())
    if raw_files:
        lines += ["| File | Bytes | SHA-256 (first 16) |", "| --- | ---: | --- |"]
        for path in raw_files:
            lines.append(
                f"| `{path.relative_to(root)}` | {path.stat().st_size} | "
                f"`{file_digest(path)[:16]}` |"
            )
    else:
        lines.append("No raw files yet. Run `scan2bim fetch all`.")

    lines += ["", "## Control measurements", ""]
    if control is None:
        lines.append("No control file found. The cloud is unverified.")
    else:
        lines += [
            f"- Surveyed on: {control.surveyed_on or 'not recorded'}",
            f"- Instrument: {control.instrument or 'not recorded'}",
            f"- Rooms: {len(control.rooms)}",
            f"- Storey height measurements: {len(control.storey_heights)}",
            f"- Wall thicknesses: {len(control.walls)}",
            f"- Control distances: {len(control.control_distances)}",
        ]

    if findings is not None:
        lines += ["", "### Validation", "", f"Overall: **{worst(findings)}**", ""]
        if findings:
            lines += ["| Severity | Code | Subject | Message |", "| --- | --- | --- | --- |"]
            for finding in findings:
                message = finding.message.replace("|", "/")
                lines.append(
                    f"| {finding.severity} | {finding.code} | {finding.subject} | {message} |"
                )
        else:
            lines.append("No issues found.")

    lines += ["", "## Cloud verification", ""]
    if verification is None:
        lines.append("Not run. Without it, no accuracy claim can be made about this model.")
    else:
        lines += [
            f"- Allowance: {verification.tolerance_mm:.0f} mm + "
            f"{verification.tolerance_pct:.2f}% of the measured length",
            f"- Control distances: {len(verification.comparisons)}",
            f"- Scale factor: {verification.scale_factor:.4f} "
            f"+/- {verification.scale_standard_error * 100:.2f}% (1 sigma)",
            f"- RMS deviation, raw: {verification.rms_deviation_mm:.1f} mm",
            f"- RMS deviation, after scaling: {verification.residual_rms_mm:.1f} mm",
            (
                f"- Datum line height spread: {verification.level_spread_mm:.0f} mm"
                if verification.level_spread_mm is not None
                else "- Datum line height spread: not measured, so cloud tilt is unknown"
            ),
            f"- Verdict: **{'pass' if verification.passed else 'fail'}**",
            "",
            verification.advice,
            "",
            "These figures describe the control lines only. Distances between points cannot "
            "reveal rotation, tilt or local warping, so they are a lower bound on the error "
            "elsewhere in the cloud, not a guarantee about it.",
            "",
        ]
        if verification.comparisons:
            lines += [
                "| Control distance | Measured (mm) | Cloud (mm) | Deviation (mm) | Allowed (mm) |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
            for comparison in verification.comparisons:
                lines.append(
                    f"| {comparison.distance_id} | {comparison.measured_mm:.0f} | "
                    f"{comparison.cloud_mm:.0f} | {comparison.deviation_mm:+.0f} | "
                    f"{verification.allowance_mm(comparison.measured_mm):.0f} |"
                )

    lines += [
        "",
        "## Sources and licences",
        "",
        "- Addresses and coordinates: PDOK Locatieserver (BAG), open data.",
        "- Parcel boundaries: PDOK Kadastrale Kaart WFS, open data.",
        "- Terrain and surface heights: AHN via PDOK WCS, open data.",
        "- Building models: 3DBAG (TU Delft), CC BY 4.0.",
        "",
    ]
    return "\n".join(lines)


def write(content: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
