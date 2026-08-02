# What accuracy to expect

Short version: consumer LiDAR is renovation grade, not survey grade, and the only honest way
to state what your particular scan achieved is to measure it against something better.

## Published figures

Three different things get called "accuracy" and they differ by two orders of magnitude. Keep
them apart:

| What | Figure | Note |
| --- | --- | --- |
| Single point precision (repeatability) | about 1 mm at 3 m | How consistent, not how correct |
| Systematic depth bias | 1 to 2 percent of range | Always reports surfaces closer than they are |
| Distance error at room and building scale | 3 to 20 cm over 10 to 15 m | What actually matters here |
| Usable range | about 5 m | Beyond that the depth is inferred, not measured |

The last row is the one to plan around and the best evidenced. The third row is the honest
answer to "how good is my model", and it is considerably worse than vendor material suggests.

**Acquisition mode matters more than device or app.** Published comparisons of the same iPad in
the same room find walking captures around 16 cm RMS against a terrestrial scanner, versus
about 3 cm when the device is held still at stations: a factor of six for free. Stopping and
holding at each room corner is the cheapest quality improvement available.

**Drift is not a scale error.** Independent studies measuring target-to-target distances find
deviations that flip sign across a room: one span short by 0.4 percent, another long by 1.4
percent in the same capture. A single scale factor cannot represent that, which is why this
tool reports the uncertainty of the factor alongside it and only advises rescaling when the
estimate clears its own noise.

### Where that lands on the USIBD scale

The USIBD Level of Accuracy scale runs LOA10 to LOA50, specified at the 95 percent confidence
level. LOA10 spans from a user-defined upper bound down to 5 cm; LOA20 spans 5 cm to 15 mm.

Phone LiDAR at building scale sits in **LOA10**, and the study that ran this exact benchmark
concluded that no consumer app reached any level of 5 cm or better at 95 percent confidence,
with 10 to 20 cm at two sigma being realistic. Claiming "under 51 mm" would be LOA20, one level
better, and is not supportable.

That is still enough for:

- layout, room dimensions and volumes
- routing services, checking whether things fit
- a permit drawing set
- quantity estimates for budgeting and comparing quotes

Not enough for:

- structural dimensions
- made-to-measure joinery, secondary glazing, a fitted kitchen
- anything where you order material against a modelled dimension without re-measuring

## Why this tool insists on control measurements

A point cloud has no error bars. It looks equally convincing whether it is 5 mm out or 50 mm
out. The only cheap way to find out is to measure distances by laser and compare them with the
same distances in the cloud. Long lines matter: a 12 m shot exposes scale and drift that a 2 m
shot hides.

`scan2bim control check` reports:

- the deviation per control distance against an allowance of a fixed part plus a proportional
  part, because a pure percentage is punishing on short lines and slack on long ones
- a least squares scale factor **with its standard error**, and advice to rescale only when the
  factor departs from 1 by more than three of those standard errors
- the RMS deviation both raw and after scaling, so you can see how much of the error scaling
  actually removes
- the height spread of the markers taped on the storey datum line, which is the tilt

### What this check cannot see, and it is a lot

A distance between two points does not change when you rotate or translate the cloud. So the
distance check is structurally blind to:

- **rotation and tilt.** Half a degree of tilt over a 12 m plan is 105 mm of height error, and
  Revit levels are horizontal planes. This is why the datum line markers exist: their true
  heights are equal, so any spread the cloud reports is levelling error. Measure them.
- **local warping.** Drift is path dependent; the error between two markers says nothing about
  the wall halfway between them.
- **doubled geometry** from a failed loop closure, the signature phone-scan artefact.
- **everything not on a control line**, which is almost the whole building.

Treat the reported numbers as a *lower bound* on the error, not a certificate. Four to six
lines give you three to five degrees of freedom, so an RMS from that sample carries roughly 30
percent uncertainty of its own. It is enough to catch a bad capture. It is not enough to state
a tolerance at 95 percent confidence, and this tool does not pretend otherwise.

### Picking noise is the floor

Verification by picking marker points is limited by how precisely a human can click a physical
point in a noisy cloud: realistically 20 to 30 mm per marker, so roughly 30 to 40 mm on a
distance between two of them. If the deviations you are chasing are that size, you are
measuring your own clicking.

The stronger method, for the same field effort, is **face to face**: measure clear internal
dimensions with the laser flat against the wall, then fit planes to those two wall patches in
CloudCompare and take the separation. Plane fitting averages over tens of thousands of points
and lands at a few millimetres instead of tens. Use markers for registration and for labelling
which capture is which; use faces for the metric check.

## Where national data beats your phone

For anything outdoors, stop scanning and download. AHN is a nationwide aerial LiDAR survey at
roughly ten measurements per square metre, and 3DBAG derives per-building roof geometry from
it. Both are more accurate over a garden or a roof than a handheld phone will ever be, and both
are free. Use your phone indoors, where aerial data cannot reach.

## Recording it

Whatever the numbers come out at, write them down. `scan2bim report` produces a provenance
document with the sources, hashes, control measurements and deviations, so the model can be
audited later by someone who was not there.
