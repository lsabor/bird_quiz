from django.core.management.base import BaseCommand
from django.db import transaction

from birds.models import Taxon
from scraper.ebird_api import EbirdApi


class Command(BaseCommand):
    help = "Load/refresh the full eBird taxonomy into Taxon."

    def add_arguments(self, parser):
        parser.add_argument("--refresh", action="store_true", help="Ignore cached API response")

    def handle(self, refresh, **opts):
        rows = EbirdApi(refresh=refresh).taxonomy()
        existing = {t.species_code: t for t in Taxon.objects.all()}
        new, upd = [], []
        fields = [
            "common_name",
            "scientific_name",
            "category",
            "taxon_order",
            "order",
            "family_code",
            "family_common",
            "family_scientific",
        ]
        for r in rows:
            vals = dict(
                common_name=r["comName"],
                scientific_name=r["sciName"],
                category=r["category"],
                taxon_order=r["taxonOrder"],
                order=r.get("order", ""),
                family_code=r.get("familyCode", ""),
                family_common=r.get("familyComName", ""),
                family_scientific=r.get("familySciName", ""),
            )
            t = existing.get(r["speciesCode"])
            if t is None:
                new.append(Taxon(species_code=r["speciesCode"], **vals))
            else:
                for k, v in vals.items():
                    setattr(t, k, v)
                upd.append(t)
        with transaction.atomic():
            Taxon.objects.bulk_create(new, batch_size=2000)
            Taxon.objects.bulk_update(upd, fields, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(f"Taxonomy: {len(new)} new, {len(upd)} updated"))
