# What accuracy to expect

Short version: consumer LiDAR is renovation grade, not survey grade, and the only honest way
to state what your particular scan achieved is to measure it against something better.

## Published figures

| Distance from the sensor | Typical deviation |
| --- | --- |
| up to ~3 m | around 2 cm |
| 3 to 4 m | 3 to 5 cm |
| beyond 4 to 5 m | the sensor drops out; range is roughly 5 m |

On top of that, tracking drift accumulates as you walk. App vendors report a few centimetres of
drift over a room and more across a storey. Published comparisons between capture apps disagree
with each other by large factors, which is itself the point: app benchmarks do not transfer to
your building, your lighting or your walking speed.

In the USIBD level of accuracy scale, that lands at level 1 (tolerance under 51 mm). Enough for:

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
out. The only cheap way to find out is to measure a handful of long distances by laser and
compare them with the same distances in the cloud. Long distances matter: a 12 m shot exposes
scale and drift errors that a 2 m shot hides.

`scan2bim control check` reports:

- the deviation per control distance, in millimetres and percent
- a least squares scale factor over all distances, which separates a systematic scale error
  (fixable by scaling the cloud) from random noise (not fixable)
- the RMS deviation
- a verdict against a tolerance you set

If the scale factor is consistently off by more than 0.3 percent, rescale before modelling.
If any single distance is outside your tolerance, that part of the building was captured badly
and the cloud should not be trusted there.

## Where national data beats your phone

For anything outdoors, stop scanning and download. AHN is a nationwide aerial LiDAR survey at
roughly ten measurements per square metre, and 3DBAG derives per-building roof geometry from
it. Both are more accurate over a garden or a roof than a handheld phone will ever be, and both
are free. Use your phone indoors, where aerial data cannot reach.

## Recording it

Whatever the numbers come out at, write them down. `scan2bim report` produces a provenance
document with the sources, hashes, control measurements and deviations, so the model can be
audited later by someone who was not there.
