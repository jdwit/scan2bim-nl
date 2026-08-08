# scan2bim-nl

Turn an iPhone LiDAR scan of a Dutch building into a **verified** basis for a Revit model.

A phone scan gives you shape. A laser distance meter gives you size. This tool keeps those two
apart on purpose: it structures the hand measurements, pulls the free national datasets that
are better than anything you can capture yourself, and then tells you how far your point cloud
actually deviates from reality. No API keys, no accounts: every data source used here is Dutch
open data.

```
                iPhone LiDAR scan ─────────┐
                                           ▼
  laser control measurements ──▶  scan2bim control check  ──▶  scale factor + deviations
                                           │
  PDOK / AHN / 3DBAG open data ──▶  scan2bim fetch all  ──▶  parcel, terrain, roof heights
                                           │
                                           ▼
                              Revit: point cloud + toposolid
                                           │
                                           ▼
                              scan2bim report  ──▶  provenance and accuracy
```

## Why

Consumer LiDAR reaches about 5 m, and at room and building scale published studies put the
error at 3 to 20 cm over 10 to 15 m spans, worse when you walk rather than stop and hold. That
is fine for layout, volumes, routing and a 1:100 permit set, and not fine for structural work
or made-to-measure joinery. The difference between "a scan" and "a survey" is whether you can
put a number on the deviation and say what that number does and does not cover. This tool
produces those numbers, with their uncertainty, and is explicit about the error modes a
distance check cannot see.

Documentation:
**[runbook.md](docs/runbook.md) is the step by step plan**, start there.
[workflow.md](docs/workflow.md) for the process end to end,
[measuring.md](docs/measuring.md) for the measurement protocol,
[revit.md](docs/revit.md) for building the model,
[accuracy.md](docs/accuracy.md) for what to expect and why,
[data-sources.md](docs/data-sources.md) for the endpoints and licences.

## Install

```bash
uv tool install git+https://github.com/jdwit/scan2bim-nl
# or, for development
git clone https://github.com/jdwit/scan2bim-nl && cd scan2bim-nl && make setup
```

## Quickstart

```bash
scan2bim doctor                                   # are all open data services reachable?
scan2bim project init myhouse -a "Oranjelaan 5 Hilversum"
cd myhouse
scan2bim fetch all                                # parcel, footprints, terrain, 3D buildings
scan2bim markers sheet                            # print these before the survey day
# ... survey day: fill in control/control.yaml, scan the building ...
scan2bim control validate
scan2bim control check picked.csv --units m       # picked in CloudCompare
scan2bim report --picked picked.csv
```

## What each command gives you

| Command | Output | Used for |
| --- | --- | --- |
| `project init` | folder layout, control template, survey checklist | Getting the field work right first time |
| `address search/resolve` | RD coordinates (EPSG:28992), BAG id | Anchoring the project in the national grid |
| `fetch parcel` | parcel GeoJSON and DXF | Plot boundary as surveyed data, not traced from a scan |
| `fetch footprint` | building footprints GeoJSON and DXF | The corner you anchor RD shared coordinates on |
| `markers sheet` | printable A4 markers | Named points you can find back in the cloud |
| `fetch terrain` | AHN GeoTIFF and `x,y,z` point file | Revit toposolid, garden levels, eaves and ridge check |
| `fetch building` | 3DBAG heights and CityJSON | Independent check on ridge, eaves, storeys, and the neighbours |
| `control validate` | findings table | Catches missing diagonals, unit slips, impossible heights |
| `control check` | scale factor, per-distance deviation | The verification that makes the model defensible |
| `report` | markdown provenance report | Evidence that travels with the model |

## The control file

`control/control.yaml` holds what you measured by hand, in millimetres. It is the reference the
cloud is checked against, so it wins whenever the two disagree.

```yaml
project: myhouse
instrument: Leica Disto D2
storey_heights:
  - { storey: ground, location: hall north, floor_to_ceiling_mm: 3120, floor_to_floor_mm: 3450 }
rooms:
  - { id: living, storey: ground, width_mm: 4210, length_mm: 5320,
      diagonal_a_mm: 6790, diagonal_b_mm: 6835 }
walls:
  - { id: facade-south, kind: exterior, thickness_mm: 320, measured_at: window reveal }
control_distances:
  - { id: cd-ground-1, from_marker: A, to_marker: B, length_mm: 12450, storey: ground }
```

`scan2bim control check` needs the same markers picked in the cloud, as `name,x,y,z`:

```csv
A,0.000,0.000,0.000
B,12.402,0.118,0.004
```

It reports the deviation per distance, a least squares scale factor, and a verdict against a
tolerance you choose.

## Data sources

| Source | What | Licence |
| --- | --- | --- |
| [PDOK Locatieserver](https://www.pdok.nl/) | address to RD coordinates, BAG ids | open data |
| [PDOK Kadastrale Kaart WFS](https://www.pdok.nl/) | parcel boundaries | open data |
| [AHN via PDOK WCS](https://www.ahn.nl/) | 0.5 m terrain and surface heights | open data |
| [3DBAG](https://3dbag.nl/) (TU Delft) | LoD2.2 building models | CC BY 4.0 |

Details and exact endpoints in [docs/data-sources.md](docs/data-sources.md).

## Development

```bash
make setup     # uv sync, including dev tools
make test      # pytest
make lint      # ruff check + format check
make fmt       # ruff format
make check     # lint + test, what CI runs
```

Tests never touch the network: the source modules take an `httpx.Client`, so tests inject a
`MockTransport` with recorded payloads.

## Licence

MIT. Open data used by this tool carries its own licence, see the table above.
