"""Estimate frequencies from the official API by sampling real checklists.

Slower than a bar chart import, but needs only an API key. For each of the last
N years it lists checklists submitted on each day of the trip window, opens each one,
and counts the share of complete checklists that report each species.
"""

import datetime as dt
import random
from collections import Counter

from django.core.management.base import BaseCommand

from birds.models import Taxon, TripSet
from scraper.ebird_api import EbirdApi
from scraper.frequency import store_region_frequencies


class Command(BaseCommand):
    help = "Estimate species frequency for a trip from API checklists (no login needed)."

    def add_arguments(self, parser):
        parser.add_argument("trip")
        parser.add_argument("--years", type=int, default=5)
        parser.add_argument("--max-checklists", type=int, default=300, help="Per region")
        parser.add_argument("--seed", type=int, default=0)
        parser.add_argument("--region", action="append", help="Only these region codes (default: all in trip)")

    def handle(self, trip, years, max_checklists, seed, region, **opts):
        trip = TripSet.objects.get(slug=trip)
        api = EbirdApi()
        api.require_key()
        half = trip.week_window * 7 + 3
        today = dt.date.today()
        rng = random.Random(seed)
        regions = trip.regions.all()
        if region:
            regions = regions.filter(region_code__in=region)
        for region in regions:
            subs = {}
            for y in range(today.year - years, today.year + 1):
                center = trip.target_date.replace(year=y)
                for k in range(-half, half + 1):
                    d = center + dt.timedelta(days=k)
                    if d >= today:
                        continue
                    for c in api.checklists_on(region.region_code, d.year, d.month, d.day):
                        subs[c["subId"]] = c
            ids = sorted(subs)
            rng.shuffle(ids)
            self.stdout.write(
                f"{region.region_code}: {len(ids)} checklists found, sampling {min(len(ids), max_checklists)}"
            )
            counts, n = Counter(), 0
            for sub_id in ids[:max_checklists]:
                cl = api.checklist(sub_id)
                if not cl.get("allObsReported", True):
                    continue
                n += 1
                counts.update({o["speciesCode"] for o in cl.get("obs", [])})
                if n % 25 == 0:
                    self.stdout.write(f"  {n} complete checklists processed")
            taxa = {t.species_code: t for t in Taxon.objects.filter(species_code__in=counts)}
            freqs = {taxa[c]: k / n for c, k in counts.items() if c in taxa and n}
            count = store_region_frequencies(region, n, freqs, "api_checklists")
            self.stdout.write(
                self.style.SUCCESS(f"{region.region_code}: {n} complete checklists -> {count} species stored")
            )
