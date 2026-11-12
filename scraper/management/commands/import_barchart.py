from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from birds.models import TripRegion, TripSet
from scraper.barchart import parse_barchart, week_window
from scraper.frequency import resolve_rows, store_region_frequencies


class Command(BaseCommand):
    help = (
        "Import an eBird bar chart TSV for one location of a trip (replaces that location's frequencies). "
        "Download it while logged in: https://ebird.org/barchart?r=<REGION>&bmo=1&emo=12&byr=1900&eyr=<YEAR> "
        "-> 'Download Histogram Data'."
    )

    def add_arguments(self, parser):
        parser.add_argument("trip")
        parser.add_argument("files", nargs="+", help="REGION_CODE=path/to/file.txt (region must belong to the trip)")
        parser.add_argument("--include-non-species", action="store_true", help="Keep spuh/slash/hybrid rows")
        parser.add_argument(
            "--window", type=int, help="± weeks for these files (default: the trip's); widen for sparse hotspots"
        )

    def handle(self, trip, files, include_non_species, window, **opts):
        trip = TripSet.objects.get(slug=trip)
        if not trip.target_date:
            raise CommandError("Trip has no target_date")
        weeks = week_window(trip.target_date, trip.week_window if window is None else window)
        for spec in files:
            code, sep, path = spec.partition("=")
            if not sep:
                raise CommandError(f"Expected REGION_CODE=path, got {spec!r}")
            try:
                region = trip.regions.get(region_code=code)
            except TripRegion.DoesNotExist:
                raise CommandError(f"{code} is not a region of {trip.slug}; add it with create_trip --region") from None
            bc = parse_barchart(Path(path).read_text(encoding="utf-8", errors="replace"))
            n, by_row = bc.window_stats(weeks)
            taxa, missing = resolve_rows(bc.rows)
            if missing:
                self.stderr.write(f"{code}: {len(missing)} labels not matched to the taxonomy: {missing[:8]}")
            freqs = {taxa[r]: f for r, f in by_row.items() if r in taxa}
            detail = {taxa[r].species_code: {"weeks": {w: r.values[w] for w in weeks}} for r in taxa}
            count = store_region_frequencies(
                region, n, freqs, "barchart", species_only=not include_non_species, detail=detail
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"{code}: {len(bc.rows)} rows, {n} checklists in weeks {weeks} -> {count} species stored"
                )
            )
