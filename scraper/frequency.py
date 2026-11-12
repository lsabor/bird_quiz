"""Write per-location SpeciesFrequency rows."""

from django.db import transaction

from birds.models import SpeciesFrequency, Taxon, TripRegion


def resolve_rows(rows) -> tuple[dict, list[str]]:
    """Map bar chart rows to Taxa by common name (fallback: scientific name). Returns (row->taxon, unmatched)."""
    by_common = {t.common_name: t for t in Taxon.objects.filter(common_name__in=[r.common_name for r in rows])}
    scis = [r.scientific_name for r in rows if r.scientific_name]
    by_sci = {}
    for t in Taxon.objects.filter(scientific_name__in=scis):
        if t.scientific_name not in by_sci or t.category == "species":
            by_sci[t.scientific_name] = t
    found, missing = {}, []
    for r in rows:
        t = by_common.get(r.common_name) or by_sci.get(r.scientific_name)
        if t:
            found[r] = t
        else:
            missing.append(r.common_name)
    return found, missing


@transaction.atomic
def store_region_frequencies(
    region: TripRegion,
    sample_size: int,
    freqs: dict[Taxon, float],
    source: str,
    species_only: bool = True,
    detail: dict | None = None,
) -> int:
    """Replace all frequency rows for one location."""
    region.frequencies.all().delete()
    count = 0
    for taxon, f in freqs.items():
        if f <= 0 or (species_only and taxon.category != "species"):
            continue
        SpeciesFrequency(
            region=region,
            taxon=taxon,
            frequency=f,
            sample_size=sample_size,
            source=source,
            detail=(detail or {}).get(taxon.species_code, {}),
        ).save()
        count += 1
    return count
