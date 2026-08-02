from __future__ import annotations

import io

import numpy as np
import pytest
from conftest import bytes_transport, json_transport
from PIL import Image

from scan2bim.http import SourceError, client
from scan2bim.sources import ahn, bag3d, kadaster, locatieserver

BBOX = (139600.0, 471060.0, 139720.0, 471180.0)


def test_locatieserver_parses_rd_and_address(locatieserver_payload):
    with client(json_transport(locatieserver_payload)) as c:
        hit = locatieserver.resolve_one("Oranjelaan 5 Hilversum", c=c)
    assert hit.rd_x == pytest.approx(139657.02)
    assert hit.rd_y == pytest.approx(471121.55)
    assert hit.lon == pytest.approx(5.16263667)
    assert hit.postcode == "1217LV"
    assert hit.city == "Hilversum"
    assert hit.object_id == "0402010001608901"


def test_locatieserver_without_results_raises():
    with client(json_transport({"response": {"docs": []}})) as c, pytest.raises(SourceError):
        locatieserver.resolve_one("nowhere at all", c=c)


def test_locatieserver_rejects_unparseable_point():
    payload = {"response": {"docs": [{"weergavenaam": "x", "centroide_rd": "NOT A POINT"}]}}
    with client(json_transport(payload)) as c, pytest.raises(SourceError):
        locatieserver.resolve_one("x", c=c)


def test_kadaster_summarise_and_dxf(parcel_payload, tmp_path):
    with client(json_transport(parcel_payload)) as c:
        collection = kadaster.parcels(BBOX, c=c)
    rows = kadaster.summarise(collection)
    assert rows == [
        {
            "id": "13060051870000",
            "gemeente": "Hilversum",
            "sectie": "P",
            "perceelnummer": 518,
            "oppervlakte_m2": 1600.0,
        }
    ]

    dxf = kadaster.to_dxf(collection, tmp_path / "parcels.dxf")
    text = dxf.read_text()
    assert text.startswith("0\nSECTION")
    assert text.rstrip().endswith("EOF")
    assert text.count("VERTEX") == 5
    assert "139640.000" in text


def test_kadaster_dxf_handles_multipolygon(tmp_path):
    collection = {
        "features": [
            {
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]]],
                }
            }
        ]
    }
    text = kadaster.to_dxf(collection, tmp_path / "m.dxf").read_text()
    assert text.count("VERTEX") == 4


def test_bag3d_parse_skips_building_parts(bag3d_payload):
    with client(json_transport(bag3d_payload)) as c:
        payload = bag3d.fetch(BBOX, c=c)
    buildings = bag3d.parse(payload)
    assert len(buildings) == 1
    building = buildings[0]
    assert building.storeys == 2
    assert building.roof_type == "slanted"
    assert building.height_above_ground_m == pytest.approx(8.59, abs=0.01)
    assert building.eaves_above_ground_m == pytest.approx(2.95, abs=0.01)


def _geotiff(values: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(values.astype(np.float32), mode="F").save(buffer, format="TIFF")
    return buffer.getvalue()


def test_ahn_reads_raster_and_masks_nodata():
    values = np.array([[10.0, 11.0], [12.0, 3.4028235e38]], dtype=np.float32)
    raster = ahn.read_raster(_geotiff(values), (0.0, 0.0, 1.0, 1.0))
    assert raster.shape == (2, 2)
    assert raster.pixel_size == pytest.approx(0.5)
    assert np.isnan(raster.values[1, 1])
    stats = raster.stats()
    assert stats["count"] == 3
    assert stats["relief_m"] == pytest.approx(2.0)


def test_ahn_to_xyz_uses_pixel_centres_and_drops_nodata():
    values = np.array([[10.0, 11.0], [12.0, 3.4028235e38]], dtype=np.float32)
    raster = ahn.read_raster(_geotiff(values), (100.0, 200.0, 101.0, 201.0))
    points = raster.to_xyz()
    assert points.shape == (3, 3)
    # Top-left pixel centre sits half a pixel in from the origin.
    assert points[0][0] == pytest.approx(100.25)
    assert points[0][1] == pytest.approx(200.75)
    assert points[0][2] == pytest.approx(10.0)


def test_ahn_write_points_csv(tmp_path):
    points = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    path = ahn.write_points_csv(points, tmp_path / "p.csv")
    assert path.read_text().splitlines() == ["1.000,2.000,3.000", "4.000,5.000,6.000"]


def test_ahn_suggested_step_scales_with_area():
    assert ahn.suggested_step((0, 0, 50, 50)) == 1
    assert ahn.suggested_step((0, 0, 500, 500)) > 1


def test_ahn_rejects_unknown_coverage():
    with client(bytes_transport(b"")) as c, pytest.raises(ValueError):
        ahn.fetch("nope", BBOX, c=c)


def test_ahn_detects_xml_error_disguised_as_success():
    transport = bytes_transport(b"<ExceptionReport/>", content_type="text/xml")
    with client(transport) as c, pytest.raises(SourceError, match="content-type"):
        ahn.fetch("dtm_05m", BBOX, c=c)
