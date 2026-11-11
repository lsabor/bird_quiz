from pathlib import Path

from django.core.management.base import BaseCommand

from scraper.packs import import_pack


class Command(BaseCommand):
    help = "Import a pack produced by export_pack (upserts; safe to re-run)."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, path, **opts):
        stats = import_pack(Path(path))
        self.stdout.write(
            self.style.SUCCESS(f"Imported {stats['trip']}: {stats['taxa']} species, {stats['assets']} assets")
        )
