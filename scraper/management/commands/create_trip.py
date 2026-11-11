import datetime as dt

from django.core.management.base import BaseCommand

from birds.models import TripRegion, TripSet


class Command(BaseCommand):
    help = "Create or update a TripSet (place + time of year)."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--name", required=True)
        parser.add_argument("--date", required=True, help="YYYY-MM-DD target birding date")
        parser.add_argument("--window", type=int, default=1, help="± bar-chart weeks (default 1)")
        parser.add_argument(
            "--region",
            action="append",
            default=[],
            help="eBird region or hotspot code; repeatable. Use CODE=Label to name it.",
        )

    def handle(self, slug, name, date, window, region, **opts):
        trip, created = TripSet.objects.update_or_create(
            slug=slug,
            defaults=dict(name=name, target_date=dt.date.fromisoformat(date), week_window=window),
        )
        for r in region:
            code, _, label = r.partition("=")
            TripRegion.objects.update_or_create(trip_set=trip, region_code=code, defaults={"label": label})
        regions = ", ".join(str(r) for r in trip.regions.all())
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} {trip.slug}: {regions}"))
