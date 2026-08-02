# Data sources

Every service below is Dutch open data: no API key, no account, no rate limit worth worrying
about at the scale of one building. Be polite anyway; requests carry a descriptive user agent.

## PDOK Locatieserver

Address to coordinates, and the BAG identifier of the addressable object.

```
GET https://api.pdok.nl/bzk/locatieserver/search/v3_1/free
    ?q=Oranjelaan 5 Hilversum&fq=type:adres&rows=1
    &fl=weergavenaam,centroide_rd,centroide_ll,adresseerbaarobject_id
```

Coordinates come back as WKT points in both RD (EPSG:28992, metres) and WGS84. RD is what the
rest of the pipeline uses, because everything else Dutch is in RD and metres are what a building
is measured in.

Used by: `scan2bim address search`, `scan2bim address resolve`, `scan2bim project init -a`.

## PDOK Kadastrale Kaart (WFS)

Parcel boundaries, building footprints, parcel numbers and areas.

```
GET https://service.pdok.nl/kadaster/kadastralekaart/wfs/v5_0
    ?service=WFS&version=2.0.0&request=GetFeature
    &typeNames=kadastralekaart:Perceel&outputFormat=application/json
    &srsName=EPSG:28992&bbox=<xmin>,<ymin>,<xmax>,<ymax>,EPSG:28992
```

Layers: `Perceel`, `Bebouwing`, `KadastraleGrens`, `Nummeraanduidingreeks`, `OpenbareRuimteNaam`.

Used by: `scan2bim fetch parcel`. Written as GeoJSON, and as a plain R12 DXF with one polyline
per ring so it links straight into Revit or AutoCAD in RD metres.

## AHN via PDOK (WCS)

Nationwide LiDAR height data. Two coverages, both 0.5 m:

- `dtm_05m`: terrain, ground level with objects removed
- `dsm_05m`: surface, including roofs and vegetation

```
GET https://service.pdok.nl/rws/ahn/wcs/v1_0
    ?service=WCS&version=2.0.1&request=GetCoverage&coverageId=dtm_05m
    &subset=x(<xmin>,<xmax>)&subset=y(<ymin>,<ymax>)&format=image/tiff
```

Two gotchas, both handled in `scan2bim.sources.ahn`:

- nodata is encoded as the float32 maximum (about 3.4e38), not as NaN. Left unmasked it
  destroys every statistic and produces absurd toposolids.
- errors come back with HTTP 200 and an XML body, so the content type has to be checked.

Requesting a bbox subset is easier than the raw LAZ tiles from
[GeoTiles](https://geotiles.citg.tudelft.nl/) when all you need is one plot. Reach for the raw
tiles only if you want individual returns rather than a gridded surface.

Used by: `scan2bim fetch terrain`. Writes the GeoTIFF plus an `x,y,z` point file for a Revit
toposolid, subsampled to keep the file manageable.

## 3DBAG (TU Delft)

LoD1.2, LoD1.3 and LoD2.2 models of every building in the Netherlands, generated from BAG
footprints and AHN heights.

```
GET https://api.3dbag.nl/collections/pand/items?bbox=<xmin>,<ymin>,<xmax>,<ymax>&limit=25
```

The attributes worth reading are `b3_h_maaiveld` (ground level, NAP), `b3_h_nok` (ridge),
`b3_h_dak_max` and `b3_h_dak_min` (roof extremes, the minimum being the eaves in practice),
`b3_bouwlagen` (storeys) and `b3_dak_type`. Building parts repeat their parent's identifier
with a suffix and carry no attributes, so they are skipped.

Licence: CC BY 4.0, so credit 3DBAG if you publish derived drawings.

Used by: `scan2bim fetch building`. Gives you an independent height check on your own survey,
and the neighbours' roofs for daylight and shadow questions.

## What is deliberately not used

- **BAG API of the Kadaster**: needs an API key. PDOK exposes the same data without one.
- **Matterport, Polycam cloud processing and similar**: closed pipelines. The whole point here
  is that the raw capture and the verification stay in your hands.
