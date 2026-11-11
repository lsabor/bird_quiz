from django.core.management.base import BaseCommand

from scraper.ebird_api import EbirdApi


class Command(BaseCommand):
    help = "Look up eBird region codes (subregions of a parent) or hotspots near a lat/lng."

    def add_arguments(self, parser):
        parser.add_argument("--country", help="List subnational1 regions, e.g. MA")
        parser.add_argument("--subnational1", help="List subnational2 regions, e.g. MA-07")
        parser.add_argument("--near", help="lat,lng - list hotspots nearby")
        parser.add_argument("--dist", type=int, default=25, help="km radius for --near (max 50)")

    def handle(self, country, subnational1, near, dist, **opts):
        api = EbirdApi()
        if country:
            for r in api.subregions("subnational1", country):
                self.stdout.write(f"{r['code']:<14} {r['name']}")
        if subnational1:
            for r in api.subregions("subnational2", subnational1):
                self.stdout.write(f"{r['code']:<14} {r['name']}")
        if near:
            lat, lng = (float(x) for x in near.split(","))
            spots = sorted(api.hotspots_near(lat, lng, dist), key=lambda h: -(h.get("numSpeciesAllTime") or 0))
            for h in spots:
                self.stdout.write(f"{h['locId']:<12} {h.get('numSpeciesAllTime') or 0:>4} spp  {h['locName']}")
