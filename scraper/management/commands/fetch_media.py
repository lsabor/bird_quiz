from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from birds.models import MediaAsset, MediaType, TripSet
from scraper import sources as media_sources
from scraper.http import PoliteClient


class Command(BaseCommand):
    help = "Fetch photo/audio metadata + files for every species in a trip. Resumable."

    def add_arguments(self, parser):
        parser.add_argument("trip")
        parser.add_argument("--sources", default="inaturalist,xeno_canto", help="Comma list: inaturalist, xeno_canto")
        parser.add_argument("--photos", type=int, default=15, help="Photos per species")
        parser.add_argument("--audio", type=int, default=10, help="Audio clips per species (per source)")
        parser.add_argument("--max-audio-seconds", type=int, default=60)
        parser.add_argument("--min-frequency", type=float, default=0.0)
        parser.add_argument("--species", action="append", help="Limit to species code(s)")
        parser.add_argument("--inat-near", help="lat,lng,radius_km - bias iNat media to a region")
        parser.add_argument("--xc-box", help="lat_min,lon_min,lat_max,lon_max - bias xeno-canto to a region")
        parser.add_argument("--metadata-only", action="store_true", help="Don't download files")

    def handle(
        self,
        trip,
        sources: str,
        photos,
        audio,
        max_audio_seconds,
        min_frequency,
        species,
        inat_near,
        xc_box,
        metadata_only,
        **opts,
    ):
        trip = TripSet.objects.get(slug=trip)
        srcs = {s.strip() for s in sources.split(",") if s.strip()}
        bad = srcs - {"inaturalist", "xeno_canto"}
        if bad:
            raise CommandError(f"Unknown sources: {bad}")
        geo = None
        if inat_near:
            lat, lng, r = inat_near.split(",")
            geo = {"lat": lat, "lng": lng, "radius": r}
        freqs = trip.frequencies.select_related("taxon").filter(frequency__gte=min_frequency)
        if species:
            freqs = freqs.filter(taxon__species_code__in=species)
        http = PoliteClient()
        media_root = Path(settings.MEDIA_ROOT)
        total = freqs.count()
        for i, sf in enumerate(freqs, 1):
            taxon = sf.taxon
            cands = []
            try:
                if "inaturalist" in srcs:
                    for mtype, n in ((MediaType.PHOTO, photos), (MediaType.AUDIO, audio)):
                        if not n:
                            continue
                        found = media_sources.inaturalist(http, taxon, mtype, n, geo) if geo else []
                        if len(found) < n:  # top up from anywhere in the world
                            seen = {c["external_id"] for c in found}
                            extra = media_sources.inaturalist(http, taxon, mtype, n, None)
                            found += [c for c in extra if c["external_id"] not in seen][: n - len(found)]
                        cands += found
                if "xeno_canto" in srcs and audio:
                    cands += media_sources.xeno_canto(http, taxon, audio, max_audio_seconds, xc_box)
            except Exception as e:  # keep going; rerun picks up where we left off
                self.stderr.write(f"  {taxon.common_name}: metadata error {e!r}")
            got = 0
            for c in cands:
                ext = c.pop("ext")
                key = dict(source=c.pop("source"), external_id=c.pop("external_id"), media_type=c.pop("media_type"))
                asset, _ = MediaAsset.objects.update_or_create(**key, defaults=c)
                if not metadata_only and not asset.file:
                    rel = Path(taxon.species_code) / f"{asset.source}_{asset.media_type}_{asset.external_id}.{ext}"
                    try:
                        http.download(asset.download_url, media_root / rel)
                        asset.file = str(rel)
                        asset.save(update_fields=["file"])
                    except Exception as e:
                        self.stderr.write(f"  download failed {asset.download_url}: {e!r}")
                        continue
                got += 1
            self.stdout.write(f"[{i}/{total}] {taxon.common_name}: {got} assets")
        self.stdout.write(self.style.SUCCESS("Done."))
