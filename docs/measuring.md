# The measurement protocol

How to measure a building so that the numbers survive scrutiny months later, when the walls
are open and nobody remembers what was meant by "3.15 m".

The short version of the whole document: **measure the control network before you scan, work
from one datum per storey, and write down where each measurement was taken.** A dimension
without a location is a rumour.

## Equipment

| Item | Why |
| --- | --- |
| Laser distance meter | Every dimension over a metre. A tape sags and reads short on long shots |
| 5 m tape measure | Reveals, thicknesses, anything where the laser cannot see its own target |
| Cross line laser | The datum line per storey; also floor level differences between rooms |
| Masking tape and printed markers | Named, re-findable points, both for the tape and for the cloud |
| Marker pen and clipboard | Numbers go on paper first. Phones die, paper does not |
| Phone with free storage, power bank | Scanning eats gigabytes and battery |
| Target card (white A5 on stiff board) | Laser shots over 10 m onto a dark or absent surface |

A laser distance meter costs around 100 euro and is the single highest-value purchase in this
entire workflow.

## The two rules

**1. Control before detail.** Long measurements first, small ones after. If your long
dimensions are right, a wrong room dimension is a local error. If your long dimensions are
wrong, everything downstream inherits it and nothing reveals that.

**2. One datum per storey.** Set the cross line laser to a horizontal line at a round height,
by convention 1000 mm above the finished floor at the entrance of that storey. This is the
*metre line*. Mark it on the wall in every room. Every vertical measurement then references
that line rather than the local floor, which is exactly what you want in a building where the
floor is not flat and not level.

With the metre line you get floor level differences for free: measure from the line down to the
floor in each room; the differences between those readings are the level differences.

## Order of work

Do not deviate from this order. Each step depends on the one before.

### 1. Walk through and sketch (30 minutes)

Freehand plan per storey, no scale. Name every room and write the names on the sketch. Those
names are used in `control/control.yaml`, in the scan file names, and in the photos. Consistent
naming is worth more than neat handwriting.

While walking, note: where the building phases change (a 1900 house with a 1914 extension has
two different wall thicknesses), where floors slope, where you cannot reach.

### 2. Markers (30 minutes)

Tape a marker at each end of every control distance you plan to take. Name them per storey:
`A`, `B`, `C` on the ground floor, `A1`, `B1` on the first, and so on.

- Put them at a consistent height, around 1.2 m, on a flat piece of wall.
- Choose points that will still exist after the scan: not on furniture, not on a door leaf.
- Corners are good anchors, but tape the marker slightly off the corner so both the laser and
  the scanner can actually see it.
- Photograph each marker with the room in shot, so you can find it back in the cloud.

Leave the markers up until scanning is finished. They are the link between the two datasets.

### 3. Control network (45 to 60 minutes per storey)

Four to six long shots per storey, of which at least two are full diagonals across the floor
plan. Aim for the longest lines the building allows, through open doors if necessary.

Technique:

- Shoot from the reference face of the instrument, and know which face that is. Getting the
  10 cm body length wrong is the most common single error in laser measuring.
- Keep the beam perpendicular to the target. An angled shot always reads long.
- Over 10 m, or onto a dark surface, hold the target card at the marker.
- Take each shot twice. If the readings differ by more than 3 mm, take a third.

Write these into `control_distances` in the control file, in millimetres, with the marker names
and a description that lets someone else repeat the shot.

### 4. Rooms (10 minutes per room)

Per room: width, length and **both** diagonals, all at a consistent height, roughly 1 m above
the floor and not against the skirting. Skirtings, pipe boxings and plaster build-up will
otherwise turn up as phantom geometry.

The diagonals are not optional. Width and length alone describe a rectangle, and in a pre-war
building the room is not a rectangle. Two diagonals that differ by 45 mm tell you the room is a
parallelogram, which is information you need before you order a kitchen for it.

If furniture blocks a diagonal, measure it in two parts along the same straight line and note
that you did.

### 5. Heights (15 minutes per storey)

From the metre line, in at least three places per room:

- down to the finished floor
- up to the ceiling

Floor-to-ceiling is the sum. Floor-to-floor needs the floor construction thickness: measure it
in the stairwell opening, at a hatch, or through a service penetration. If you genuinely cannot
reach it, record floor-to-ceiling only and leave `floor_to_floor_mm` empty rather than guessing;
`scan2bim control validate` would flag an impossible pair anyway.

Expect variation of a few centimetres across one storey. That is not an error to be averaged
away, it is the building. Record all of it; you pick one Revit level later, deliberately.

### 6. Wall thicknesses (20 minutes)

- Exterior walls: in a window reveal, per facade, and separately per building phase. Note
  whether the reveal is plastered, because that is 10 to 20 mm of the reading.
- Interior walls: in a door opening, one per wall type.
- Note the construction where visible: solid brick, cavity, timber stud, and the direction of
  the floor joists if a hatch or a damaged ceiling shows it.

### 7. Openings (5 minutes per type, then count)

Measure one of each type precisely, then record which type each opening is:

- structural opening width and height, not just the visible frame
- sill height above the finished floor
- reveal depth
- glazing bar layout, and whether the glass is special (stained, patterned, historic)
- direction of opening, and hinge side

### 8. Stairs (10 minutes)

Number of risers, total rise, going, width, and the stairwell opening in the floor above.
Number of risers times individual rise must equal the floor-to-floor height; that is a free
check on step 5.

### 9. Photographs (30 minutes)

Per room: four corners, ceiling, floor, and each opening straight on. Plus every marker, every
measurement point, and anything odd: cracks, damp stains, previous alterations, service runs.

Name them `<storey>-<room>-<subject>.jpg` and drop them in `raw/photos/`. In six months these
are worth more than you expect, and they cost nothing today.

### 10. Validate before you leave

```bash
scan2bim control validate
```

Failures are impossible values, almost always a unit slip. Warnings show where the survey is
thin. Fix both while you can still walk back into the room. This is the entire reason the
command exists.

## Then scan

Only now. The scanning protocol is in [workflow.md](workflow.md) and the field version is in
the checklist that `scan2bim project init` writes into your project.

## Time budget

For a house of roughly 200 m2 over three levels, in one day with two people:

| Block | Time |
| --- | --- |
| Sketch and markers | 1 hour |
| Control network, all storeys | 2 hours |
| Rooms, heights, walls, openings, stairs | 3 hours |
| Photographs | 0.5 hour |
| Scanning | 2 hours |
| Facade photo series | 0.5 hour |

Alone, add half again. Two people is genuinely faster here, because one holds the target and
one reads, and because someone dictating numbers makes fewer transcription errors than someone
writing their own.

## Mistakes that cost the most

- **Scanning first, measuring second.** The scan then dictates the model, and there is nothing
  left to check it against.
- **No diagonals.** The model comes out square, the building is not, and the error surfaces
  when something is manufactured to fit.
- **Measuring from the floor instead of a datum.** Every reading inherits the local floor slope
  and the errors compound differently in each room.
- **One height per storey.** You will not know whether the ceiling drops 40 mm across the
  living room, and the ceiling finish detail depends on it.
- **Unrecorded locations.** "Exterior wall 320" is useless when the 1914 extension turns out to
  be 220.
- **Rounding on site.** Write what the instrument says. Rounding is a decision for the model,
  not for the notebook.
