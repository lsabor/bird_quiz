import pytest

from birds.models import MediaAsset, SpeciesFrequency, Taxon, TripRegion, TripSet
from scraper.packs import export_pack, import_pack


@pytest.mark.django_db
def test_roundtrip(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "m1"
    (tmp_path / "m1/abc").mkdir(parents=True)
    (tmp_path / "m1/abc/x.jpg").write_bytes(b"img")
    trip = TripSet.objects.create(slug="t", name="T")
    TripRegion.objects.create(trip_set=trip, region_code="MA-07")
    tx = Taxon.objects.create(
        species_code="abc", common_name="A", scientific_name="A a", category="species", taxon_order=1
    )
    SpeciesFrequency(trip_set=trip, taxon=tx, frequency=0.2).save()
    MediaAsset.objects.create(taxon=tx, media_type="photo", source="inaturalist", external_id="1", file="abc/x.jpg")
    export_pack(trip, tmp_path / "p.tar.gz")

    for m in (MediaAsset, SpeciesFrequency, TripSet, Taxon):
        m.objects.all().delete()
    settings.MEDIA_ROOT = tmp_path / "m2"
    stats = import_pack(tmp_path / "p.tar.gz")
    assert stats == {"trip": "t", "taxa": 1, "assets": 1}
    assert (tmp_path / "m2/abc/x.jpg").read_bytes() == b"img"
    assert SpeciesFrequency.objects.get().rarity == "common"
    assert TripSet.objects.get().regions.get().region_code == "MA-07"
