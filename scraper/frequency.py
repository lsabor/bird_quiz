"""Write SpeciesFrequency rows for a trip from per-region {sci_or_code: freq} maps."""

from django.db import transaction

from birds.models import SpeciesFrequency, Taxon, TripSet


def resolve_taxa(sci_names) -> dict[str, Taxon]:
    taxa = {}
    for t in Taxon.objects.filter(scientific_name__in=list(sci_names)):
        # Prefer full species when a sci name is shared across categories
        if t.scientific_name not in taxa or t.category == "species":
            taxa[t.scientific_name] = t
    return taxa


@transaction.atomic
def store_frequencies(
    trip: TripSet, per_region: dict[str, tuple[int, dict[Taxon, float]]], source: str, species_only: bool = True
) -> int:
    """per_region: region_code -> (sample_size, {taxon: freq}). Combines regions with max."""
    combined: dict[Taxon, dict] = {}
    for code, (n, freqs) in per_region.items():
        for taxon, f in freqs.items():
            if species_only and taxon.category != "species":
                continue
            entry = combined.setdefault(taxon, {"frequency": 0.0, "sample_size": 0, "detail": {}})
            entry["detail"][code] = {"frequency": round(f, 5), "sample_size": n}
            if f >= entry["frequency"]:
                entry["frequency"], entry["sample_size"] = f, n
    trip.frequencies.filter(source=source).delete()
    count = 0
    for taxon, e in combined.items():
        if e["frequency"] <= 0:
            continue
        SpeciesFrequency(trip_set=trip, taxon=taxon, source=source, **e).save()
        count += 1
    return count
