# The workflow, end to end

From an empty building to a Revit model you can defend. The tooling in this repo covers the
parts a computer is good at; the rest is discipline on the day.

## 0. Before the survey day

```bash
scan2bim doctor
scan2bim project init myhouse -a "Oranjelaan 5 Hilversum"
cd myhouse
scan2bim fetch all
```

You now have:

- `project.toml` with the RD coordinates of the building
- `raw/parcels.geojson` and `derived/parcels.dxf`: the plot boundary as surveyed data
- `raw/ahn_dtm_05m.tif` and `raw/ahn_dsm_05m.tif`: terrain and surface heights
- `derived/ahn_dtm_05m_points.csv`: an `x,y,z` file for a Revit toposolid
- `raw/3dbag.city.json` plus a printed table of ridge, eaves and storey counts
- `control/control.yaml` waiting to be filled in
- `docs/checklist.md`, the survey day checklist

Print the checklist. Read the 3DBAG table before you go: it tells you roughly what ridge and
eaves height to expect, so a gross mistake on the day is obvious immediately.

## 1. The control network (first, before any scanning)

This is the step that separates a survey from a souvenir. Tape a named marker at each end of
every planned control distance and measure with a laser distance meter:

- four to six long shots per storey, including at least two full diagonals
- width, length and **both** diagonals per room
- floor-to-ceiling at three or more places per storey, plus floor-to-floor
- exterior wall thickness in a window reveal, per facade and per building phase
- window openings per type, staircase, basement height, floor level differences

Write it into `control/control.yaml` and check it before you leave the building:

```bash
scan2bim control validate
```

Warnings tell you where the survey is thin. Failures are impossible values, usually a unit
slip. Fix them while you can still walk back to the room.

## 2. Scanning

One scan per room, two to four minutes each, walking slowly at 1.2 to 1.5 m and keeping 1.5 to
3 m from surfaces. Close a loop: end where you started. Start each new scan inside the previous
room so the scans overlap in the doorway. Stairwells, basement and attic separately.

Export from the app:

- SiteScape exports `.rcp` directly, which Revit links without conversion, plus `.e57`
- other apps export `.las` or `.e57`, which Autodesk ReCap indexes into `.rcp`

Copy everything into `raw/scans/` the same evening, and keep the raw exports. A raw cloud can be
reprocessed in five years with better software; a finished model cannot.

## 3. Facades

LiDAR will not reach a full facade, and sunlight degrades it further. Photograph instead: 60 to
80 percent overlap, three heights, overcast light, and a known length in shot as scale
reference. Process in RealityScan (free below a revenue threshold). Photogrammetry has no
inherent scale, so that reference object is not optional.

## 4. Verify the cloud

Open the cloud in CloudCompare, pick each marker point, and export the picked points as
`name,x,y,z`. Then:

```bash
scan2bim control check picked.csv --units m
```

You get, per control distance, the deviation in millimetres and percent, plus a least squares
scale factor over all of them and a verdict against your tolerance (1 percent by default).

- Within tolerance, no systematic error: model on this cloud.
- Within tolerance, but a consistent scale offset above 0.3 percent: scale the cloud by the
  reported factor first (CloudCompare: Edit > Multiply/Scale).
- Outside tolerance: rescan that area, or demote the cloud to a shape reference and take
  dimensions from the control list.

This is the number that lets you write "as-built to within x" instead of hoping.

## 5. Into Revit

1. `Insert > Point Cloud`, link the `.rcp` (link, do not import).
2. Set the project base point on a physically identifiable point and fix true north. Write down
   which point you used; every later addition depends on it.
3. Create levels at the **measured** storey heights, not at default values.
4. Model walls onto the cloud with the measured thicknesses. Where cloud and control
   measurement disagree, the control measurement wins.
5. Terrain: `Massing & Site > Toposolid > Create from Import > Points File`, using
   `derived/ahn_dtm_05m_points.csv`, comma delimited, units in metres.
6. Parcel boundary: link `derived/parcels.dxf`.
7. Cross-check ridge and eaves height against the 3DBAG table.

### One coordinate system, not two

AHN, 3DBAG and the parcel are in RD/NAP. Your interior scans are in an arbitrary local frame.
Couple them once, deliberately, through Revit shared coordinates, and record how you did it.
Skip this and the terrain and the building will drift apart, which makes every derived
dimension suspect.

## 6. Publish the evidence

```bash
scan2bim report --picked picked.csv
```

`reports/provenance.md` lists the data sources with retrieval hashes, the control measurements,
the validation findings and the verification result. Keep it next to the model. A model that
claims to be as-built should carry its evidence, and this is the cheapest way to do that.

## What this does not do

- It does not model for you. Scan to BIM remains manual work.
- It does not replace a laser scanner or a survey firm for structural or made-to-measure work.
- It does not touch the `.rvt` file. Everything here stops at the point where Revit takes over.
