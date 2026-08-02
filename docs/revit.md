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
  survives the next person.

## 1. Coordinates: one system, once

This is the step that quietly ruins models, so do it deliberately.

Revit gets numerically unstable when geometry sits far from its internal origin. Dutch RD
coordinates are around 139000, 471000, which is 150 km away. So do **not** move the building to
RD. Instead:

1. Model the building near the internal origin.
2. `Manage > Coordinates > Specify Coordinates at Point`, click a known point (a facade corner
   you can identify in the parcel data) and type its RD easting, northing and NAP height.
3. Set true north via `Manage > Position > Rotate True North`.

Revit now knows where the building is without moving it there. Everything you link afterwards
with "Auto - By Shared Coordinates" lands in the right place, and everything you export inherits
it.

Write the chosen point and its coordinates into the project information. Every later addition,
by you or by a modeller you hire, must use the same one.

## 2. Link the surveyed context

Order matters: context first, so the building is placed onto something rather than beside it.

**Parcel boundary.** `Insert > Link CAD`, `derived/parcels.dxf`, units metres, positioning
`Auto - By Shared Coordinates`, place at the site level. Lock it.

**Terrain.** `Massing & Site > Toposolid > Create from Import > Points File`, choose
`derived/ahn_dtm_05m_points.csv`, comma delimited, units metres. The z values are metres NAP,
which is why step 1 included a height. Use `ahn_dsm_05m_points.csv` only if you want vegetation
and roofs as a sanity check; it is not a terrain surface.

**Point cloud.** `Insert > Point Cloud`, link the file (link, never import). Revit links
`.rcp` and `.rcs` natively, and from Revit 2025 also `.e57` directly.

If the cloud came out of `scan2bim control check` with a systematic scale error above 0.3
percent, scale it in CloudCompare before linking. Revit will not fix that for you.

### Do you need ReCap?

Often not. Check in this order, and settle it before you pay for anything:

1. **Does your capture app export `.rcp`?** SiteScape does, on its free tier. Then you link
   it and ReCap never enters the picture. This is the strongest practical argument for
   choosing SiteScape over the alternatives.
2. **Are you on Revit 2025 or newer?** Then `.e57` links directly. Verify it yourself in ten
   seconds: `Insert > Point Cloud` and open the file type dropdown. That dialog is more
   authoritative than any article, including this one.
3. **Neither?** Then you need ReCap Pro (subscription, roughly 50 dollars a month or 405 a
   year, with a 30 day trial) or a third party plugin such as Undet or nCircle. Public
   sources disagree about what the free ReCap tier still allows, so check your own Autodesk
   account rather than trusting a blog.

ReCap still earns its place when you have many separate scan positions that need registering
into one coordinate system, when you want noise removal and cropping before modelling, or
when the cloud is large enough that Revit needs the spatial index to stay responsive. For a
house captured room by room with an app that already merges its own scans, none of those
apply.

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

1. Everything surveyed goes on phase **Existing**.
2. What comes out is marked **Demolished** in the New Construction phase.
3. New work is created in phase **New Construction**.
4. Create view templates: `Bestaand` (phase Existing, phase filter showing existing only) and
   `Nieuw` (phase New Construction, filter showing new plus existing plus demolished).

Duplicate each plan, section and elevation for both phases. Change a wall once, and both
drawing sets stay consistent. That consistency is the entire argument for modelling instead of
drawing.

## 10. Rooms and schedules

Place rooms with the names from your survey sketch. Then:

- **Area check.** A room schedule with areas, compared against the NEN 2580 measurement report
  if the property has one. Revit measures to the wall face by default; the Dutch standard has
  its own rules, so expect a difference of a few percent and understand it rather than chasing
  it.
- **Quantities.** Wall area by type, floor area by finish, window and door schedules. Good
  enough to budget with and to compare quotes against.
- **Not good enough to order with.** Re-measure on site at the moment of ordering and add
  waste. The model gives you the argument, not the purchase order.

## 11. Views and sheets

The minimum set for a renovation of a listed building:

- Floor plan per storey, existing and proposed, 1:100 (1:50 for detailed areas)
- Two sections, at least one through the stairwell
- Four elevations
- Site plan with the parcel boundary and the terrain
- A demolition plan if the permit requires it separately

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
