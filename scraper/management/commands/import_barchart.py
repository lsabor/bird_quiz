from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from birds.models import TripSet
from scraper.barchart import parse_barchart, week_window
from scraper.frequency import resolve_taxa, store_frequencies


class Command(BaseCommand):
    help = (
        "Import eBird bar chart TSV(s) for a trip. Download them while logged in to eBird: "
        "Explore > Bar Charts > pick region > 'Download Histogram Data'. "
        "Pass each as REGION_CODE=path/to/file.txt."
    )

    def add_arguments(self, parser):
        parser.add_argument("trip")
        parser.add_argument("files", nargs="+", help="REGION_CODE=path (or just path; code taken from trip)")
        parser.add_argument("--include-non-species", action="store_true")

    def handle(self, trip, files, include_non_species, **opts):
        trip = TripSet.objects.get(slug=trip)
        if not trip.target_date:
            raise CommandError("Trip has no target_date")
        weeks = week_window(trip.target_date, trip.week_window)
        per_region = {}
        for i, spec in enumerate(files):
            code, sep, path = spec.partition("=")
            if not sep:
                path, code = spec, (list(trip.regions.values_list("region_code", flat=True)) + [f"file{i}"])[i]
            bc = parse_barchart(Path(path).read_text(encoding="utf-8", errors="replace"))
            n, by_sci = bc.window_stats(weeks)
            taxa = resolve_taxa(by_sci)
            missing = [s for s in by_sci if s not in taxa]
            if missing:
                self.stderr.write(f"{code}: {len(missing)} names not in taxonomy (run sync_taxonomy?): {missing[:5]}")
            per_region[code] = (n, {taxa[s]: f for s, f in by_sci.items() if s in taxa})
            self.stdout.write(f"{code}: {len(bc.rows)} taxa, {n} checklists in weeks {weeks}")
        count = store_frequencies(trip, per_region, "barchart", species_only=not include_non_species)
        self.stdout.write(self.style.SUCCESS(f"Stored {count} species frequencies for {trip.slug}"))
