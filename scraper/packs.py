"""Portable trip 'packs': manifest.json + media files in a .tar.gz. DB-agnostic."""

import datetime as dt
import io
import json
import tarfile
from pathlib import Path

from django.conf import settings
from django.db import transaction

from birds.models import MediaAsset, SpeciesFrequency, Taxon, TripRegion, TripSet

PACK_VERSION = 2  # 2: frequencies are per region
TAXON_FIELDS = [
    "species_code",
    "common_name",
    "scientific_name",
    "category",
    "taxon_order",
    "order",
    "family_code",
    "family_common",
    "family_scientific",
]
ASSET_FIELDS = [
    "media_type",
    "source",
    "external_id",
    "source_url",
    "download_url",
    "file",
    "rating",
    "contributor",
    "license",
    "location",
    "obs_date",
    "tags",
    "excluded",
]


def _ser(v):
    return v.isoformat() if isinstance(v, dt.date) else v


def export_pack(trip: TripSet, out: Path, sources: list[str] | None = None, include_files: bool = True) -> dict:
    freqs = list(SpeciesFrequency.objects.filter(region__trip_set=trip).select_related("taxon", "region"))
    taxa = list({f.taxon_id: f.taxon for f in freqs}.values())
    assets = MediaAsset.objects.filter(taxon__in=taxa).exclude(file="").select_related("taxon")
    if sources:
        assets = assets.filter(source__in=sources)
    manifest = {
        "pack_version": PACK_VERSION,
        "exported": dt.datetime.now(dt.UTC).isoformat(),
        "trip": {
            "slug": trip.slug,
            "name": trip.name,
            "target_date": _ser(trip.target_date),
            "week_window": trip.week_window,
            "notes": trip.notes,
            "regions": [{"region_code": r.region_code, "label": r.label} for r in trip.regions.all()],
        },
        "taxa": [{k: getattr(t, k) for k in TAXON_FIELDS} for t in taxa],
        "frequencies": [
            {
                "species_code": f.taxon.species_code,
                "region_code": f.region.region_code,
                "frequency": f.frequency,
                "sample_size": f.sample_size,
                "source": f.source,
                "detail": f.detail,
            }
            for f in freqs
        ],
        "assets": [
            {"species_code": a.taxon.species_code, **{k: _ser(getattr(a, k)) for k in ASSET_FIELDS}} for a in assets
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    media_root = Path(settings.MEDIA_ROOT)
    with tarfile.open(out, "w:gz") as tar:
        data = json.dumps(manifest, indent=1).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        if include_files:
            for a in manifest["assets"]:
                p = media_root / a["file"]
                if p.exists():
                    tar.add(p, arcname=f"media/{a['file']}")
    return {"taxa": len(taxa), "assets": len(manifest["assets"])}


def _safe_members(tar: tarfile.TarFile):
    for m in tar.getmembers():
        if m.isfile() and m.name.startswith("media/") and ".." not in Path(m.name).parts:
            yield m


@transaction.atomic
def import_pack(path: Path) -> dict:
    media_root = Path(settings.MEDIA_ROOT)
    with tarfile.open(path, "r:*") as tar:
        manifest = json.load(tar.extractfile("manifest.json"))
        if manifest.get("pack_version", 0) > PACK_VERSION:
            raise ValueError("Pack is from a newer version of bird_quiz; update first.")
        for m in _safe_members(tar):
            dest = media_root / Path(m.name).relative_to("media")
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(tar.extractfile(m).read())

    taxa = {}
    for t in manifest["taxa"]:
        code = t.pop("species_code")
        taxa[code], _ = Taxon.objects.update_or_create(species_code=code, defaults=t)
    tr = manifest["trip"]
    regions = tr.pop("regions")
    tr["target_date"] = dt.date.fromisoformat(tr["target_date"]) if tr["target_date"] else None
    trip, _ = TripSet.objects.update_or_create(slug=tr.pop("slug"), defaults=tr)
    for r in regions:
        TripRegion.objects.update_or_create(trip_set=trip, region_code=r["region_code"], defaults={"label": r["label"]})
    region_objs = {r.region_code: r for r in trip.regions.all()}
    for f in manifest["frequencies"]:
        code = f.pop("species_code")
        # v1 packs had one combined row per trip; attach those to the first region
        region = region_objs.get(f.pop("region_code", None)) or region_objs[regions[0]["region_code"]]
        sf = SpeciesFrequency.objects.filter(region=region, taxon=taxa[code]).first() or SpeciesFrequency(
            region=region, taxon=taxa[code]
        )
        for k, v in f.items():
            setattr(sf, k, v)
        sf.save()
    for a in manifest["assets"]:
        code = a.pop("species_code")
        if a.get("obs_date"):
            a["obs_date"] = dt.date.fromisoformat(a["obs_date"])
        key = {k: a.pop(k) for k in ("source", "external_id", "media_type")}
        MediaAsset.objects.update_or_create(**key, defaults={**a, "taxon": taxa[code]})
    return {"trip": trip.slug, "taxa": len(taxa), "assets": len(manifest["assets"])}
