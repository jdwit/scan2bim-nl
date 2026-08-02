# Building the model in Revit

From the survey data to a complete as-built model, in the order that avoids rework. Written for
a Dutch renovation project, so it assumes RD coordinates, a permit set that needs existing and
proposed drawings, and a building that is not square.

Everything here is manual modelling. `scan2bim` prepares and verifies the inputs; Revit is
where a person makes decisions.

## 0. Before you place a single wall

- **Units in millimetres.** Manage > Project Units > Length, format to the millimetre.
- **Start from a template you will keep using.** The Dutch content pack from your Autodesk
  account, or NLRS if you will exchange the model with other offices. For a single private
  project NLRS is heavy; the discipline that matters is consistent naming, not the standard.
- **Decide the level of detail now.** As-built LOD 200: volumes, storey heights, room
  dimensions, wall thicknesses, opening positions and sizes, roof shape, stairs. No
  construction details, no mouldings. Write it in the project information so the decision
  survives the next person. For a listed building, see section 9 first: the details this
  level excludes are exactly what a monument assessment turns on, so plan a separate set of
  measured details at 1:5 or 1:20 for the elements under discussion.
- **Set the phase before you model anything.** New elements take the phase of the *active
  view*, and stock templates put every view on New Construction. Create your `Bestaand` views
  with Phase set to Existing and work in those from the start. Discovering this after modelling
  the whole building means reassigning Phase Created on every element, which is the exact
  rework this document exists to prevent.

## 1. Coordinates: one system, once

This is the step that quietly ruins models, so do it deliberately.

Revit gets numerically unstable when geometry sits far from its internal origin. Autodesk's
limit is **10 miles, about 16 km**, for all geometry, with a 20 mile work plane. Dutch RD
coordinates put a building in Hilversum roughly **490 km** from the RD false origin, thirty
times past the limit. So do **not** move the building to RD. Instead:

1. Model the building near the internal origin.
2. `Manage > Coordinates > Specify Coordinates at Point`, click a known point (a facade corner
   you can identify in the parcel data) and type its RD easting, northing and NAP height.
3. Set true north via `Manage > Position > Rotate True North`.

Two details decide whether this works:

- **Clip state of the survey point.** If the survey point is clipped when you specify
  coordinates, Revit *moves* the survey point. Unclipped, it stays put and only its reported
  values change. Get this wrong and you have dragged your reference hundreds of kilometres.
- **Visibility.** Once RD is set, the survey point conceptually sits ~490 km away. Turn its
  visibility off, or the first "zoom to fit" will show you an empty screen and a very small
  building.

Revit now knows where the building is without moving it there. Everything you link afterwards
with "Auto - By Shared Coordinates" lands in the right place, and everything you export inherits
it.

**Everything this tool exports is in a local frame by default**, with the project origin
subtracted, precisely so that it lands near the internal origin rather than being silently
re-centred by Revit. Use `--rd` if you want absolute coordinates for GIS work instead.

Write the chosen point and its coordinates into the project information. Every later addition,
by you or by a modeller you hire, must use the same one.

## 2. Link the surveyed context

Order matters: context first, so the building is placed onto something rather than beside it.

**Parcel boundary.** `Insert > Link CAD`, `derived/parcels.dxf`, units metres, positioning
`Auto - By Shared Coordinates`, place at the site level. Lock it.

**Terrain.** `Massing & Site tab > Model Site panel > Toposolid > (Create from Import)`, then
`(Create from CSV)` on the contextual tab. Choose `derived/ahn_dtm_05m_points.csv` and set the
units to metres in the Format dialog. Z values are metres NAP, which is why step 1 included a
height.

Two things Autodesk does quietly here: **anything over 10,000 points is downsampled**, and
points far from the model are re-centred with the georeferencing thrown away. `fetch terrain`
handles both, by staying under the limit and exporting in the local frame. Use
`ahn_dsm_05m_points.csv` only as a sanity check on roofs and vegetation; it is not terrain.

**Point cloud.** `Insert > Point Cloud`, link the file (link, never import). Revit 2024, 2025
and 2026 all offer exactly two file types in that dialog: `Point Cloud Projects (*.rcp)` and
`Point Clouds (*.rcs)`. **There is no direct `.e57` import**, whatever secondary sources claim.

After linking, before modelling: move and rotate the cloud so it sits on your levels and faces
true north, then **pin it**. A phone capture has an arbitrary origin and heading, and a cloud
that shifts halfway through modelling is worse than no cloud.

If the cloud came out of `scan2bim control check` with a systematic scale error above 0.3
percent, scale it in CloudCompare before linking. Revit will not fix that for you.

### Do you need ReCap?

Sometimes, and the honest answer is more awkward than it first looks. Revit reads only `.rcp`
and `.rcs`. CloudCompare, where the verification and any cleaning or rescaling happen, cannot
write either format. So the moment you *modify* the cloud, you need something that can produce
`.rcp` again.

There is exactly one ReCap-free route, and it is narrow:

1. Capture with an app that exports `.rcp` directly. SiteScape does, on its free tier.
2. Export the same capture a second time as `.e57` or `.las`, and do the verification on that
   copy in CloudCompare. Verification only reads coordinates, so this costs nothing.
3. If the verdict is **pass with no systematic scale error**, link the untouched `.rcp`. The
   cloud you verified and the cloud you model on are the same data.

If the verdict says rescale, or the capture needs registering or cleaning first, that route
closes. Then it is ReCap Pro (subscription, roughly 50 dollars a month or 405 a year, with a
30 day trial) or a third party plugin such as Undet or nCircle. Public sources disagree about
what the free ReCap tier still allows, so check your own Autodesk account rather than a blog.

Plan for this before the survey, not on the day you open Revit. If the budget cannot stretch to
ReCap, bias every decision on the survey day towards a cloud that will not need correcting:
short scans, generous overlap, one capture per storey where the app allows it.

## 3. Levels

Create one level per storey, at the measured floor-to-floor heights from the control file.

- Name them for the building, not for Revit defaults: `BG`, `1e`, `zolder`, `kelder`.
- Where floor-to-ceiling varies across a storey, pick the level that matters structurally
  (usually the floor) and record the ceiling variation as a note or as separate ceilings. Do
  not average the variation away silently.
- Cross-check: number of stair risers times rise should equal your floor-to-floor.

Levels are the one thing that is genuinely painful to change later, because everything is
hosted on them. Get them from the measurements, not from the cloud.

## 4. Walls

Set up wall types first, with the **measured** thicknesses, one per building phase if they
differ. Name them so the thickness is visible: `Ext 320 solid brick 1900`,
`Ext 220 brick 1914`, `Int 100 stud`.

Then model, in a plan view with the view range cut plane at about 1.2 m, with the point cloud
visible:

- Draw wall by wall along the cloud. Do not use the rectangle tool, and turn off angular
  snapping. Every rectangle you draw is a lie about a pre-war building.
- Set the location line to the correct face (usually the interior face, because that is what
  you measured) rather than the wall centre.
- Where the cloud and a control measurement disagree, the control measurement wins. Always.
  Adjust the wall to the measured dimension and let the cloud show the discrepancy.
- Keep walls storey-by-storey rather than multi-storey, so a later alteration on one floor does
  not reach through the building.

For the out-of-square rooms your diagonals exposed: model the deviation. A room that is 45 mm
out over 6 m is a wall that is 0.4 degrees off, and that is exactly the sort of thing that
decides whether a fitted wardrobe fits.

## 5. Floors, ceilings and level differences

Floors per storey, with the measured construction thickness. Where rooms sit at different
levels, use separate floor elements at their measured heights rather than one floor with a
shape edit, so the difference stays legible in a section.

Ceilings as separate elements at their measured heights. In an old house the ceiling is often
not parallel to the floor; two elements let you show that honestly.

## 6. Roof

The roof of a 1900 villa is the hardest part and the least visible in an interior scan.

- Start with `Roof by Footprint` for the main volume, using the eaves height and the pitch from
  your facade measurements.
- Check the ridge against the 3DBAG figure that `scan2bim fetch building` printed
  (`b3_h_nok` minus `b3_h_maaiveld`). If your modelled ridge is more than a few decimetres off,
  something is wrong with your pitch or your eaves height, and it is cheaper to find that now.
- Dormers as separate roofs plus wall openings.
- If you photographed the facades, the photogrammetry mesh linked as context is far better
  evidence for the roof geometry than an interior cloud.

## 7. Openings

Build one family per window and door type with the measured structural opening, sill height and
glazing bar layout. Do not place generic families with round numbers and intend to fix them
later; you will not, and the schedules will be wrong.

Place them from the cloud position, then set the sill height from the control measurement.
Name types so the schedule reads as an order list: `W-01 1180x2150 6-pane`.

## 8. Stairs

Stair by component, with the measured risers, rise and going. Model the stairwell opening in
the floor above as a shaft, so it stays correct when the floor changes.

## 9. Phasing: this is what produces the permit set

For a Dutch permit application you deliver *bestaande toestand* and *nieuwe toestand*. Revit
phasing gives you both from one model, which is the main reason to have a model at all.

1. Everything surveyed goes on phase **Existing** (set the view phase first, see section 0).
2. What comes out is marked **Demolished** in the New Construction phase.
3. New work is created in phase **New Construction**.
4. View templates: `Bestaand` (Phase = Existing, Phase Filter = `Show Complete`) and `Nieuw`
   (Phase = New Construction, Phase Filter = `Show Previous + Demo`, which is the filter that
   actually renders demolished elements).
5. `Manage > Phases > Graphic Overrides` to get the Dutch drawing convention: demolished in
   one colour, new in another. Without overrides the model cannot produce a sloop/nieuw
   drawing that reads correctly.

Three traps that cost people a resubmission:

- **Rooms are phase specific.** A room placed in Existing does not exist in New Construction.
  You place them twice and schedule them per phase, which also means the area comparison in
  section 10 is per phase.
- **Schedules have their own Phase and Phase Filter.** A quantity take-off silently reports one
  phase; check the field before you believe a number.
- **Toposolids are phased too**, which matters as soon as an extension changes ground level.
  Levels and grids are not phased, so they are shared across both sets.

Duplicate each plan, section and elevation for both phases. Change a wall once, and both
drawing sets stay consistent. That consistency is the entire argument for modelling instead of
drawing.

## 9b. What this model cannot tell you about services

A phone scan sees surfaces. It does not see pipes in floors, cables in walls, or the flue in a
chimney. For MEP coordination the model gives you accurate voids, floor build-ups, shaft
positions and ceiling heights, and nothing at all about what is already inside the construction.

So: model the space, not the services. Record visible fixtures and penetrations while you are
in the building, photograph every opened floor during demolition, and treat existing service
routes as unknown until they are exposed. Anything else is coordination against guesswork.

## 10. Rooms and schedules

Place rooms with the names from your survey sketch. Then:

- **Area check.** A room schedule with areas, compared against the NEN 2580 measurement report
  if the property has one. Before blaming the standard, check
  `Architecture > Room & Area > Area and Volume Computations`: the room boundary setting (wall
  finish, centre, core) changes every area in the schedule. Then expect a residual difference
  of a few percent, because NEN 2580 has its own counting rules, and understand it rather than
  chasing it.
- **Quantities.** Wall area by type, floor area by finish, window and door schedules. Good
  enough to budget with and to compare quotes against.
- **Not good enough to order with.** Re-measure on site at the moment of ordering and add
  waste. The model gives you the argument, not the purchase order.

## 11. Views and sheets

Under the Omgevingswet the application goes through the Omgevingsloket, and work on a
municipal monument needs a **monumentenactiviteit** alongside the building activity. The
indieningsvereisten are set by the municipality, so read theirs; the set below is what they
generally ask for.

- **Bestaand and nieuw for every drawing type**: floor plans, sections *and* elevations. Only
  supplying existing plans plus proposed elevations is the most common reason a set comes back.
- Floor plan per storey, 1:100, or 1:50 where it matters
- At least two sections, one through the stairwell
- All elevations, existing and proposed
- **Situatietekening** at 1:500 or 1:1000 with north arrow, cadastral boundaries and the
  **peilmaat relative to NAP or street level**
- A separate demolition drawing where work is removed
- **Detail drawings at 1:5 or 1:20** for the monument-critical elements: window profiles,
  glazing bars, cornices, plasterwork. This is above the LOD 200 the rest of the model sits at,
  and it is deliberate: these details are what the monument committee actually assesses.

Two things this workflow does not produce and the municipality will still want:

- **Bouwhistorisch onderzoek.** For a monument, and always for partial demolition, expect a
  cultural-historical or building-historical report following the Richtlijnen bouwhistorisch
  onderzoek. A point cloud is not a substitute; it is an input.
- **Bbl compliance evidence**: daylight area per habitable space, ventilation capacity, fire
  compartmentation, stair dimensions and headroom at renovation level, plus a structural
  calculation for any extension. The model supports these; it does not answer them.

Put dimension strings on the plans that repeat your control distances. That way anyone reading
the drawing can check the model against the survey with a scale rule.

## 12. Quality control before you hand anything over

Work through this before the model leaves your hands:

- [ ] Every control distance from `control/control.yaml` measured in the model and within
      tolerance
- [ ] Storey heights match the measured values, and the variation is documented
- [ ] Ridge and eaves within a few decimetres of the 3DBAG figures
- [ ] Room areas compared against the measurement report, differences explained
- [ ] Wall thicknesses match the survey, per building phase
- [ ] Shared coordinates set, and the reference point recorded in project information
- [ ] Terrain and parcel line up with the building, not next to it
- [ ] Phasing set, so both drawing sets generate correctly
- [ ] `scan2bim report` regenerated and stored with the model

## 13. Handover

What travels with the model:

- the native `.rvt`, and the Revit version it was made in
- an `.ifc` 4 export, because that outlives your licence
- PDF plots of every plan, section and elevation
- `reports/provenance.md`
- the raw scans and photos, not just the processed ones

A model without its provenance is an opinion. With it, it is a survey.

## Working with an external modeller

If someone else builds the model, give them all of the above plus one instruction in writing:
**the control measurements outrank the point cloud, and where the two disagree they must flag
it rather than choose.** Silent reconciliation is how a model ends up looking finished and
being wrong.

Agree in advance on: the Revit version, millimetres, the coordinate reference point, the level
of detail, and the deliverables list above.
