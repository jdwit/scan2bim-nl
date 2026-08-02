"""Command line interface."""

from __future__ import annotations

import json as jsonlib
from importlib import resources
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from scan2bim import config
from scan2bim import control as control_mod
from scan2bim import markers as markers_mod
from scan2bim import report as report_mod
from scan2bim import verify as verify_mod
from scan2bim.http import SourceError, client
from scan2bim.sources import ahn, bag3d, kadaster, locatieserver

app = typer.Typer(
    help="Turn an iPhone LiDAR scan of a Dutch building into a verified basis for Revit.",
    no_args_is_help=True,
    add_completion=False,
)
project_app = typer.Typer(help="Create and inspect a survey project.", no_args_is_help=True)
address_app = typer.Typer(help="Look up addresses and coordinates.", no_args_is_help=True)
fetch_app = typer.Typer(help="Pull open data for the project location.", no_args_is_help=True)
control_app = typer.Typer(help="Validate and verify control measurements.", no_args_is_help=True)
markers_app = typer.Typer(help="Printable markers for the survey.", no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(address_app, name="address")
app.add_typer(fetch_app, name="fetch")
app.add_typer(control_app, name="control")
app.add_typer(markers_app, name="markers")

console = Console()
err = Console(stderr=True)

CONTROL_FILE = Path("control") / "control.yaml"


def _fail(message: str) -> None:
    err.print(f"[red]error[/red] {message}")
    raise typer.Exit(code=1)


def _load_project() -> tuple[Path, config.Project]:
    try:
        return config.load()
    except FileNotFoundError as exc:
        _fail(str(exc))
        raise  # unreachable, keeps type checkers happy


def _template(name: str) -> str:
    return resources.files("scan2bim.templates").joinpath(name).read_text(encoding="utf-8")


@project_app.command("init")
def project_init(
    name: Annotated[str, typer.Argument(help="Project name, used as the folder name")],
    address: Annotated[
        str | None, typer.Option("--address", "-a", help="Dutch address to resolve immediately")
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option("--directory", "-d", help="Project folder itself, instead of ./<name>"),
    ] = None,
) -> None:
    """Create a project folder with the standard layout, a control template and a checklist."""
    root = (directory or Path.cwd() / name).resolve()
    if (root / config.PROJECT_FILE).exists():
        _fail(f"{root / config.PROJECT_FILE} already exists")
    root.mkdir(parents=True, exist_ok=True)
    config.create_layout(root)

    project = config.Project(name=name, address=address)
    if address:
        with client() as http:
            try:
                hit = locatieserver.resolve_one(address, c=http)
            except SourceError as exc:
                _fail(str(exc))
            project.address = hit.display_name
            project.postcode = hit.postcode
            project.city = hit.city
            project.rd_x = hit.rd_x
            project.rd_y = hit.rd_y
            project.bag_object_id = hit.object_id

    config.save(root, project)
    control_path = root / CONTROL_FILE
    if not control_path.exists():
        control_path.write_text(
            _template("control.example.yaml").replace("CHANGE-ME", name), encoding="utf-8"
        )
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "checklist.md").write_text(_template("checklist.md"), encoding="utf-8")

    console.print(f"[green]created[/green] {root}")
    console.print(f"  control template : {CONTROL_FILE}")
    console.print("  survey checklist : docs/checklist.md")
    if project.has_location:
        console.print(
            f"  location         : {project.address} (RD {project.rd_x:.1f}, {project.rd_y:.1f})"
        )
    else:
        console.print('  location         : not set, run `scan2bim address resolve "<address>"`')


@project_app.command("show")
def project_show(
    json_out: Annotated[bool, typer.Option("--json", help="Machine readable output")] = False,
) -> None:
    """Show the current project."""
    root, project = _load_project()
    if json_out:
        console.print_json(jsonlib.dumps({"root": str(root), **project.model_dump()}))
        return
    table = Table(show_header=False, box=None)
    table.add_row("root", str(root))
    for key, value in project.model_dump(exclude_none=True).items():
        table.add_row(key, str(value))
    console.print(table)


@address_app.command("search")
def address_search(
    query: Annotated[str, typer.Argument(help="Free text address query")],
    rows: Annotated[int, typer.Option("--rows", "-n", help="Number of results")] = 5,
) -> None:
    """Search Dutch addresses and show their RD coordinates."""
    with client() as http:
        try:
            hits = locatieserver.search(query, c=http, rows=rows)
        except SourceError as exc:
            _fail(str(exc))
    if not hits:
        _fail(f"No address found for {query!r}")
    table = Table("address", "RD x", "RD y", "lon", "lat")
    for hit in hits:
        table.add_row(
            hit.display_name,
            f"{hit.rd_x:.2f}",
            f"{hit.rd_y:.2f}",
            f"{hit.lon:.6f}",
            f"{hit.lat:.6f}",
        )
    console.print(table)


@address_app.command("resolve")
def address_resolve(
    query: Annotated[str, typer.Argument(help="Address to store on the project")],
) -> None:
    """Resolve an address and write the coordinates into project.toml."""
    root, project = _load_project()
    with client() as http:
        try:
            hit = locatieserver.resolve_one(query, c=http)
        except SourceError as exc:
            _fail(str(exc))
    project.address = hit.display_name
    project.postcode = hit.postcode
    project.city = hit.city
    project.rd_x = hit.rd_x
    project.rd_y = hit.rd_y
    project.bag_object_id = hit.object_id
    config.save(root, project)
    console.print(f"[green]resolved[/green] {hit.display_name}")
    console.print(f"  RD {hit.rd_x:.2f}, {hit.rd_y:.2f}  (EPSG:28992)")


@fetch_app.command("parcel")
def fetch_parcel(
    radius: Annotated[float | None, typer.Option("--radius", help="Half-width in metres")] = None,
    dxf: Annotated[bool, typer.Option("--dxf/--no-dxf", help="Also write a DXF")] = True,
    elevation: Annotated[
        float, typer.Option("--elevation", help="Z for the DXF, in metres NAP")
    ] = 0.0,
    absolute: Annotated[
        bool, typer.Option("--rd/--local", help="Absolute RD coordinates instead of local")
    ] = False,
) -> None:
    """Cadastral parcels around the project, as GeoJSON and a DXF in the local frame."""
    root, project = _load_project()
    bbox = _bbox(project, radius)
    with client() as http:
        try:
            collection = kadaster.parcels(bbox, c=http)
        except SourceError as exc:
            _fail(str(exc))
    raw = kadaster.write_geojson(collection, root / "raw" / "parcels.geojson")
    console.print(f"[green]saved[/green] {raw.relative_to(root)}")
    if dxf:
        out = kadaster.to_dxf(
            collection,
            root / "derived" / "parcels.dxf",
            layer="PERCEEL",
            elevation=elevation,
            offset=_origin(project, absolute),
        )
        console.print(f"[green]saved[/green] {out.relative_to(root)}")

    rows = kadaster.summarise(collection)
    if rows:
        table = Table("gemeente", "sectie", "nummer", "m2")
        for row in rows:
            table.add_row(
                str(row["gemeente"]),
                str(row["sectie"]),
                str(row["perceelnummer"]),
                f"{row['oppervlakte_m2']:.0f}" if row["oppervlakte_m2"] else "-",
            )
        console.print(table)


@fetch_app.command("footprint")
def fetch_footprint(
    radius: Annotated[float | None, typer.Option("--radius", help="Half-width in metres")] = None,
    dxf: Annotated[bool, typer.Option("--dxf/--no-dxf", help="Also write a DXF")] = True,
    elevation: Annotated[
        float, typer.Option("--elevation", help="Z for the DXF, in metres NAP")
    ] = 0.0,
    absolute: Annotated[
        bool, typer.Option("--rd/--local", help="Absolute RD coordinates instead of local")
    ] = False,
) -> None:
    """Cadastral building footprints: what you align the model to when setting RD coordinates."""
    root, project = _load_project()
    bbox = _bbox(project, radius)
    with client() as http:
        try:
            collection = kadaster.buildings(bbox, c=http)
        except SourceError as exc:
            _fail(str(exc))
    raw = kadaster.write_geojson(collection, root / "raw" / "footprints.geojson")
    console.print(f"[green]saved[/green] {raw.relative_to(root)}")
    if dxf:
        out = kadaster.to_dxf(
            collection,
            root / "derived" / "footprints.dxf",
            layer="BEBOUWING",
            elevation=elevation,
            offset=_origin(project, absolute),
        )
        console.print(f"[green]saved[/green] {out.relative_to(root)}")
    console.print(
        f"[dim]{len(collection.get('features', []))} footprint(s). Pick a corner you can also "
        "identify in the point cloud; that is your shared coordinates point.[/dim]"
    )


@fetch_app.command("terrain")
def fetch_terrain(
    coverage: Annotated[
        str, typer.Option("--coverage", help="dtm_05m (ground) or dsm_05m (surface)")
    ] = "dtm_05m",
    radius: Annotated[float | None, typer.Option("--radius", help="Half-width in metres")] = None,
    step: Annotated[
        int | None,
        typer.Option("--step", help="Sample every Nth pixel; default stays under Revit's limit"),
    ] = None,
    absolute: Annotated[
        bool, typer.Option("--rd/--local", help="Absolute RD coordinates instead of local")
    ] = False,
) -> None:
    """AHN height data for the plot: a GeoTIFF plus an x,y,z point file for a Revit toposolid."""
    root, project = _load_project()
    bbox = _bbox(project, radius)
    with client() as http:
        try:
            payload = ahn.fetch(coverage, bbox, c=http)
        except (SourceError, ValueError) as exc:
            _fail(str(exc))

    tif_path = root / "raw" / f"ahn_{coverage}.tif"
    tif_path.parent.mkdir(parents=True, exist_ok=True)
    tif_path.write_bytes(payload)
    console.print(f"[green]saved[/green] {tif_path.relative_to(root)}")

    raster = ahn.read_raster(payload, bbox)
    chosen_step = step if step is not None else ahn.suggested_step(bbox)
    points = raster.to_xyz(step=chosen_step)
    ox, oy = _origin(project, absolute)
    csv_path = ahn.write_points_csv(
        points, root / "derived" / f"ahn_{coverage}_points.csv", offset=(ox, oy, 0.0)
    )
    console.print(f"[green]saved[/green] {csv_path.relative_to(root)}  ({len(points)} points)")

    stats = raster.stats()
    table = Table("metric", "value")
    table.add_row("raster", f"{raster.shape[1]} x {raster.shape[0]} px at {raster.pixel_size} m")
    table.add_row("sampling", f"every {chosen_step} px")
    table.add_row("min height", f"{stats['min_m']:.2f} m NAP")
    table.add_row("max height", f"{stats['max_m']:.2f} m NAP")
    table.add_row("relief", f"{stats['relief_m']:.2f} m")
    frame = "absolute RD" if absolute else f"local, origin at RD {ox:.2f}, {oy:.2f}"
    table.add_row("frame", frame)
    console.print(table)
    console.print(
        "[dim]Revit: Massing & Site > Toposolid > Create from Import > Create from CSV, "
        "comma delimited, units in metres. Revit downsamples above "
        f"{ahn.REVIT_POINT_LIMIT:,} points.[/dim]"
    )


@fetch_app.command("building")
def fetch_building(
    radius: Annotated[float | None, typer.Option("--radius", help="Half-width in metres")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum buildings")] = 25,
) -> None:
    """3DBAG models around the project: ridge and eaves heights to check your own survey against."""
    root, project = _load_project()
    bbox = _bbox(project, radius)
    with client() as http:
        try:
            payload = bag3d.fetch(bbox, c=http, limit=limit)
        except SourceError as exc:
            _fail(str(exc))
    path = bag3d.write_features(payload, root / "raw" / "3dbag-features.json")
    console.print(f"[green]saved[/green] {path.relative_to(root)}")
    if bag3d.truncated(payload, limit):
        console.print(
            f"[yellow]warning[/yellow] more buildings exist than the limit of {limit}; "
            "raise --limit or narrow --radius"
        )

    buildings = bag3d.parse(payload)
    if not buildings:
        console.print("[yellow]no buildings returned for this area[/yellow]")
        return
    table = Table("id", "storeys", "roof", "ground (NAP)", "ridge (NAP)", "height", "eaves")
    for building in buildings:
        table.add_row(
            building.identificatie.replace("NL.IMBAG.Pand.", ""),
            str(building.storeys or "-"),
            building.roof_type or "-",
            f"{building.ground_level_m:.2f}" if building.ground_level_m is not None else "-",
            f"{building.ridge_height_m:.2f}" if building.ridge_height_m is not None else "-",
            f"{building.height_above_ground_m:.2f}"
            if building.height_above_ground_m is not None
            else "-",
            f"{building.eaves_above_ground_m:.2f}"
            if building.eaves_above_ground_m is not None
            else "-",
        )
    console.print(table)


@fetch_app.command("all")
def fetch_all(
    radius: Annotated[float | None, typer.Option("--radius", help="Half-width in metres")] = None,
) -> None:
    """Parcel, footprints, terrain, surface and buildings in one go."""
    fetch_parcel(radius=radius, dxf=True)
    fetch_footprint(radius=radius, dxf=True)
    fetch_terrain(coverage="dtm_05m", radius=radius, step=None)
    fetch_terrain(coverage="dsm_05m", radius=radius, step=None)
    fetch_building(radius=radius, limit=25)


@markers_app.command("sheet")
def markers_sheet(
    names: Annotated[
        list[str] | None,
        typer.Argument(help="Marker names; defaults to those used in the control file"),
    ] = None,
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output path")] = None,
) -> None:
    """Printable A4 markers, one per page, to tape at the ends of every control distance."""
    root, project = _load_project()
    chosen = list(names or [])
    if not chosen:
        control_path = root / CONTROL_FILE
        if not control_path.exists():
            _fail(f"{control_path} not found, so no marker names to print. Pass them explicitly.")
        try:
            chosen = markers_mod.names_from_control(control_mod.load(control_path))
        except ValueError as exc:
            _fail(str(exc))
    try:
        content = markers_mod.render(project.name, chosen)
    except ValueError as exc:
        _fail(str(exc))
    path = markers_mod.write(content, out or root / "derived" / "markers.html")
    console.print(f"[green]written[/green] {path.relative_to(root)}  ({len(chosen)} markers)")
    console.print(f"[dim]{', '.join(chosen)}[/dim]")
    console.print("[dim]Open it in a browser and print at 100 percent, no scaling.[/dim]")


@control_app.command("validate")
def control_validate(
    path: Annotated[Path | None, typer.Option("--file", "-f", help="Control file")] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Machine readable output")] = False,
) -> None:
    """Check the control file for gaps and impossible values."""
    root, _ = _load_project()
    target = path or root / CONTROL_FILE
    if not target.exists():
        _fail(f"{target} not found")
    try:
        control = control_mod.load(target)
    except ValueError as exc:
        _fail(str(exc))
    findings = control_mod.validate(control)
    verdict = control_mod.worst(findings)

    if json_out:
        console.print_json(
            jsonlib.dumps({"verdict": verdict, "findings": [f.as_dict() for f in findings]})
        )
    else:
        if findings:
            table = Table("severity", "code", "subject", "message")
            for finding in findings:
                colour = {"fail": "red", "warn": "yellow", "ok": "green"}[finding.severity]
                table.add_row(
                    f"[{colour}]{finding.severity}[/{colour}]",
                    finding.code,
                    finding.subject,
                    finding.message,
                )
            console.print(table)
        console.print(f"verdict: [bold]{verdict}[/bold]")
    if verdict == "fail":
        raise typer.Exit(code=1)


@control_app.command("check")
def control_check(
    picked: Annotated[Path, typer.Argument(help="CSV of picked markers: name,x,y,z")],
    path: Annotated[Path | None, typer.Option("--file", "-f", help="Control file")] = None,
    units: Annotated[
        str, typer.Option("--units", help="Units of the picked file: m, cm or mm")
    ] = "m",
    tolerance: Annotated[
        float, typer.Option("--tolerance", help="Proportional part of the allowance, in percent")
    ] = verify_mod.DEFAULT_TOLERANCE_PCT,
    tolerance_mm: Annotated[
        float, typer.Option("--tolerance-mm", help="Fixed part of the allowance, in millimetres")
    ] = verify_mod.DEFAULT_TOLERANCE_MM,
    json_out: Annotated[bool, typer.Option("--json", help="Machine readable output")] = False,
) -> None:
    """Compare cloud distances against the measured control distances."""
    root, _ = _load_project()
    target = path or root / CONTROL_FILE
    if not target.exists():
        _fail(f"{target} not found")
    try:
        control = control_mod.load(target)
        markers = verify_mod.read_markers(picked, units=units)
    except ValueError as exc:
        _fail(str(exc))
    result = verify_mod.compare(
        control, markers, tolerance_pct=tolerance, tolerance_mm=tolerance_mm
    )

    if json_out:
        console.print_json(
            jsonlib.dumps(
                {
                    "passed": result.passed,
                    "scale_factor": result.scale_factor,
                    "scale_standard_error": result.scale_standard_error,
                    "scale_is_significant": result.scale_is_significant,
                    "max_abs_deviation_pct": result.max_abs_deviation_pct,
                    "rms_deviation_mm": result.rms_deviation_mm,
                    "residual_rms_mm": result.residual_rms_mm,
                    "level_spread_mm": result.level_spread_mm,
                    "missing_markers": sorted(set(result.missing_markers)),
                    "comparisons": [
                        {
                            "id": c.distance_id,
                            "measured_mm": c.measured_mm,
                            "cloud_mm": c.cloud_mm,
                            "deviation_mm": c.deviation_mm,
                            "deviation_pct": c.deviation_pct,
                        }
                        for c in result.comparisons
                    ],
                    "advice": result.advice,
                }
            )
        )
    else:
        if result.comparisons:
            table = Table(
                "distance",
                "measured (mm)",
                "cloud (mm)",
                "deviation (mm)",
                "allowed (mm)",
            )
            for comparison in result.comparisons:
                colour = "green" if result.within_tolerance(comparison) else "red"
                table.add_row(
                    comparison.distance_id,
                    f"{comparison.measured_mm:.0f}",
                    f"{comparison.cloud_mm:.0f}",
                    f"[{colour}]{comparison.deviation_mm:+.0f}[/{colour}]",
                    f"{result.allowance_mm(comparison.measured_mm):.0f}",
                )
            console.print(table)
            console.print(
                f"scale factor      : {result.scale_factor:.4f} "
                f"+/- {result.scale_standard_error * 100:.2f}%  "
                f"({len(result.comparisons)} distances)"
            )
            console.print(f"raw rms deviation : {result.rms_deviation_mm:.1f} mm")
            console.print(f"after scaling     : {result.residual_rms_mm:.1f} mm")
            if result.level_spread_mm is not None:
                colour = (
                    "green"
                    if result.level_spread_mm <= verify_mod.LEVEL_SPREAD_NOTE_MM
                    else "yellow"
                )
                console.print(
                    f"datum line spread : [{colour}]{result.level_spread_mm:.0f} mm[/{colour}]"
                    "  (tilt relative to gravity; distances cannot see this)"
                )
            grouped = result.by_scan()
            if len(grouped) > 1:
                console.print("per capture       :")
                for label, group in sorted(grouped.items()):
                    worst_pct = max(abs(c.deviation_pct) for c in group)
                    console.print(f"  {label}: {len(group)} distance(s), worst {worst_pct:+.2f}%")
                console.print(
                    "[dim]All picked coordinates must come from one registered cloud; "
                    "distances across unaligned scans are meaningless.[/dim]"
                )
        console.print(f"verdict           : [bold]{'pass' if result.passed else 'fail'}[/bold]")
        console.print(result.advice)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("report")
def report(
    out: Annotated[Path | None, typer.Option("--out", "-o", help="Output path")] = None,
    picked: Annotated[
        Path | None, typer.Option("--picked", help="Picked markers CSV, to include verification")
    ] = None,
    units: Annotated[str, typer.Option("--units", help="Units of the picked file")] = "m",
) -> None:
    """Write a provenance report: sources, hashes, control measurements and deviations."""
    root, project = _load_project()
    control_path = root / CONTROL_FILE
    control = None
    findings = None
    verification = None
    if control_path.exists():
        try:
            control = control_mod.load(control_path)
        except ValueError as exc:
            _fail(str(exc))
        findings = control_mod.validate(control)
        if picked:
            try:
                markers = verify_mod.read_markers(picked, units=units)
            except ValueError as exc:
                _fail(str(exc))
            verification = verify_mod.compare(control, markers)

    content = report_mod.build(
        project, root, control=control, findings=findings, verification=verification
    )
    path = report_mod.write(content, out or root / "reports" / "provenance.md")
    console.print(f"[green]written[/green] {path.relative_to(root)}")


@app.command("doctor")
def doctor() -> None:
    """Check that every open data service is reachable. No API keys are involved anywhere."""
    checks = [
        (
            "PDOK Locatieserver",
            lambda http: locatieserver.search("Dam 1 Amsterdam", c=http, rows=1),
        ),
        (
            "PDOK Kadastrale Kaart",
            lambda http: kadaster.parcels((121000, 487000, 121100, 487100), c=http),
        ),
        (
            "AHN (PDOK WCS)",
            lambda http: ahn.fetch("dtm_05m", (121000, 487000, 121050, 487050), c=http),
        ),
        ("3DBAG", lambda http: bag3d.fetch((121000, 487000, 121100, 487100), c=http, limit=1)),
    ]
    failures = 0
    with client() as http:
        for name, call in checks:
            try:
                call(http)
            except Exception as exc:
                failures += 1
                console.print(f"[red]fail[/red] {name}: {exc}")
            else:
                console.print(f"[green]ok  [/green] {name}")
    if failures:
        raise typer.Exit(code=1)


def _origin(project: config.Project, absolute: bool) -> tuple[float, float]:
    """The offset subtracted from exported coordinates.

    Revit re-centres imported geometry that sits far from its internal origin, and RD
    coordinates are hundreds of kilometres out. Exporting in a local frame keeps every file in
    the same place, predictably. `--rd` opts back into absolute coordinates for GIS use.
    """
    if absolute or not project.has_location:
        return (0.0, 0.0)
    assert project.rd_x is not None and project.rd_y is not None
    return (project.rd_x, project.rd_y)


def _bbox(project: config.Project, radius: float | None) -> tuple[float, float, float, float]:
    try:
        return project.bbox(radius)
    except ValueError as exc:
        _fail(str(exc))
        raise


if __name__ == "__main__":  # pragma: no cover
    app()
