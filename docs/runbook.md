# Runbook

The whole process as numbered steps, with the command to run, what you should see, and how to
know the step is finished. Follow it top to bottom.

The other documents explain *why*: [measuring.md](measuring.md) for technique,
[revit.md](revit.md) for the model, [accuracy.md](accuracy.md) for what the numbers mean.

---

## Phase A. Preparation, any time before the survey

### A1. Install and check the services

```bash
uv tool install git+https://github.com/jdwit/scan2bim-nl
scan2bim doctor
```

**Done when:** four green `ok` lines. No API keys are needed anywhere; a failure here is the
service being down or your network, not a missing account.

### A2. Create the project

```bash
scan2bim project init myhouse -a "Oranjelaan 5 Hilversum"
cd myhouse
```

**Done when:** the address printed back matches the building and the RD coordinates look
plausible (five and six digits). If the address is ambiguous, run `scan2bim address search` to
see the candidates and then `scan2bim address resolve` with a sharper query.

### A3. Pull the open data

```bash
scan2bim fetch all
```

**Done when:** you have `raw/parcels.geojson`, `raw/footprints.geojson`, both AHN GeoTIFFs,
`raw/3dbag.city.json`, and the derived DXF and point files. Widen with `--radius 80` if the plot
is larger than 60 m from the address point.

**Read the 3DBAG table now.** It gives you the expected ridge and eaves height. Take those two
numbers to the building; if your own measurements disagree wildly, you know on the day rather
than three weeks later.

### A4. Plan the control network on paper

Sketch each storey freehand. Draw in the long shots you intend to take: four to six per storey,
at least two full diagonals, using the longest lines the building allows. Name the endpoints
`A`, `B`, `C` on the ground floor, `A1`, `B1` on the first, and so on.

Write those planned distances into `control/control.yaml` now, with `length_mm: 0`. You are
filling in a form on the day rather than inventing a scheme while standing in a cold house.

### A5. Print the markers

```bash
scan2bim markers sheet
```

**Done when:** `derived/markers.html` opens in a browser and shows one page per marker. Print at
100 percent, no scaling. The red circle marks the exact point you measure from and pick later.

### A6. Pack

Laser distance meter, tape measure, cross line laser, printed markers, masking tape, marker pen,
the printed `docs/checklist.md`, clipboard, phone with free storage, power bank, target card.

---

## Phase B. The survey day

Order matters. Do not start scanning early; a scan without control measurements cannot be
verified, and you will not get a second empty building.

### B1. Walk through and sketch (30 min)

Name every room on the sketch. Those names are used in the control file, the scan file names and
the photos. Note where building phases change, where floors slope, what you cannot reach.

### B2. Tape the markers (30 min)

At each planned endpoint, about 1.2 m high, on flat wall, red circle over the exact point.
Photograph each one with the room in shot. Leave them up until scanning is finished.

### B3. Set the metre line (15 min per storey)

Cross line laser, horizontal, 1000 mm above the finished floor at the storey entrance. Mark it in
every room. Every vertical measurement from now on references this line, not the local floor.

### B4. Control distances (45-60 min per storey)

Measure each planned shot twice; a third time if the two readings differ by more than 3 mm.
Fill in `length_mm` and the `photo` field.

### B5. Rooms, heights, walls, openings, stairs (3 hours)

Per room: width, length and **both** diagonals. Per storey: heights at three or more places,
from the metre line. Wall thicknesses in window reveals, per facade and per building phase.
One measurement per opening type. Stair risers, rise, going, stairwell opening.

### B6. Vertical control (20 min)

The weak point of every phone scan is the connection between storeys, because the scanner is
carried up a stairwell it cannot see well. Do not rely on it:

- Floor-to-floor per storey, measured directly in the stairwell opening or through a hatch.
- The stair check: number of risers times rise must equal floor-to-floor.
- If the stairwell is open over more than one storey, run a single long vertical shot from the
  lowest floor to the highest ceiling and record it as a control distance of its own.

Storeys are stacked on these numbers in Revit. They will not come out of the cloud.

### B7. Validate before you leave (5 min)

```bash
scan2bim control validate
```

**Done when:** no `fail` findings. Warnings are for you to judge; failures are impossible
values and mean a transcription error, which is a five minute fix now and a re-visit later.

### B8. Scan (2 hours)

One scan per room, two to four minutes each, at 1.2 to 1.5 m, 1.5 to 3 m from surfaces, closing
a loop. Overlap through doorways. Stairwell, basement and attic separately.

Record in `control/control.yaml` which capture each control distance sits in, using the `scan`
field. That is what lets the verification tell you *where* a problem is.

**Both markers of a control distance must be visible in the same scan**, or in a set of scans
you will register into one cloud. Two markers picked in two never-aligned scans produce a
distance between unrelated coordinate systems: a plausible number that means nothing.

### B9. Facades (30 min)

Photo series around the building, 60 to 80 percent overlap, three heights, overcast light. Put a
known length in shot. Tape two markers on one facade at a measured distance apart, and record
that as a control distance too; it is how you verify the photogrammetry, which otherwise has no
scale at all.

### B10. Before you drive away

Walk the checklist. Every control distance written down and photographed, every room scanned,
attic and basement covered, markers still in place in the last scan.

---

## Phase C. Processing, the same week

### C1. Copy the raw data off the phone

Into `raw/scans/` and `raw/photos/`, the same evening. Keep the raw exports, not just whatever
you convert them into.

### C2. Register and clean (CloudCompare)

Align the room scans into one cloud with point pair picking, refine with ICP, then crop away
noise behind glass, mirrors and everything outside the building.

Skip the align step only if your capture app already produced one merged cloud for the whole
storey.

### C3. Pick the markers

Point picking tool, one point per marker, at the centre of the red circle. Export as
`name,x,y,z` to `picked.csv`. The names must match the control file exactly.

### C4. Verify

```bash
scan2bim control check picked.csv --units m
```

Read the verdict:

| Result | Action |
| --- | --- |
| Pass, no systematic error | Model on this cloud |
| Pass, scale error above 0.3 percent | Scale by the reported factor in CloudCompare, then re-run |
| Fail on one or two distances | That area was captured badly. Rescan it, or take those dimensions from the control list only |
| Fail across the board | Check units first, then registration. A whole-cloud failure is usually one of those two |

If you labelled the `scan` field, the output breaks the deviations down per capture, so you can
see which room is the problem rather than guessing.

### C5. Facade photogrammetry

Process in RealityScan. Scale it using the facade control distance from B9, then verify the
same way.

---

## Phase D. The model

Full detail in [revit.md](revit.md). The order that avoids rework:

1. **D1.** Units to millimetres, level of detail written into the project information.
2. **D2.** Shared coordinates: model near the internal origin, then
   `Manage > Coordinates > Specify Coordinates at Point` on a footprint corner from
   `derived/footprints.dxf`. Record which corner, in the project information.
3. **D3.** Link the context: parcel DXF, footprint DXF, terrain from
   `derived/ahn_dtm_05m_points.csv`, then the point cloud.
4. **D4.** Levels at the **measured** floor-to-floor heights.
5. **D5.** Wall types with the measured thicknesses, one per building phase.
6. **D6.** Model walls onto the cloud, out of square where the building is out of square.
7. **D7.** Floors, ceilings, roof. Cross-check the ridge against 3DBAG.
8. **D8.** Openings as families with the measured dimensions, then stairs.
9. **D9.** Phasing: Existing, Demolished, New. This is what produces both permit drawing sets.
10. **D10.** Rooms and schedules; compare areas against the measurement report if there is one.
11. **D11.** Work through the QA checklist in revit.md before anything leaves your hands.

---

## Phase E. Publish the evidence

```bash
scan2bim report --picked picked.csv
```

**Done when:** `reports/provenance.md` contains the source hashes, the control measurements, the
validation findings and the verification result. Store it with the model and hand it over with
the `.rvt`, the `.ifc`, the PDF plots and the raw scans.

---

## Time budget

| Phase | Effort |
| --- | --- |
| A. Preparation | 1 to 2 hours, at your desk |
| B. Survey day | 8 to 9 hours for ~200 m2 with two people |
| C. Processing | half a day |
| D. Modelling | days to weeks, depending on the building and who does it |
| E. Report | minutes |

## The five things that go wrong

1. **Scanning before measuring.** Nothing left to verify against.
2. **Markers picked across unregistered scans.** Numbers that look right and are not.
3. **Relying on the cloud for storey heights.** The vertical link is the weakest part of any
   phone capture. Measure it.
4. **No diagonals.** The model comes out square and the building is not.
5. **Never running the verification.** Then it is a scan, not a survey, and nobody can tell the
   difference by looking.
