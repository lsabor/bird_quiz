from pathlib import Path

from django.core.management.base import BaseCommand

from birds.models import TripSet
from scraper.packs import export_pack


class Command(BaseCommand):
    help = "Export a trip (species, frequencies, media metadata + files) to a portable .tar.gz pack."

    def add_arguments(self, parser):
        parser.add_argument("trip")
        parser.add_argument("--out", help="Default: packs/<trip>.tar.gz")
        parser.add_argument("--sources", help="Comma list to include (e.g. inaturalist,xeno_canto for a CC-only pack)")
        parser.add_argument("--no-files", action="store_true", help="Manifest only")

    def handle(self, trip, out, sources, no_files, **opts):
        trip = TripSet.objects.get(slug=trip)
        out = Path(out or f"packs/{trip.slug}.tar.gz")
        stats = export_pack(trip, out, sources.split(",") if sources else None, include_files=not no_files)
        self.stdout.write(self.style.SUCCESS(f"Wrote {out} ({stats['taxa']} species, {stats['assets']} assets)"))
