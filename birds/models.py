from django.conf import settings
from django.db import models


class Taxon(models.Model):
    """One row of the eBird taxonomy."""

    species_code = models.CharField(max_length=16, unique=True)
    common_name = models.CharField(max_length=128, db_index=True)
    scientific_name = models.CharField(max_length=128, db_index=True)
    category = models.CharField(max_length=16)  # species, issf, spuh, slash, hybrid...
    taxon_order = models.FloatField(db_index=True)
    order = models.CharField(max_length=64, blank=True)
    family_code = models.CharField(max_length=32, blank=True)
    family_common = models.CharField(max_length=128, blank=True)
    family_scientific = models.CharField(max_length=128, blank=True)

    class Meta:
        ordering = ["taxon_order"]

    def __str__(self):
        return f"{self.common_name} ({self.scientific_name})"

    @property
    def genus(self) -> str:
        return self.scientific_name.split(" ")[0]


class TripSet(models.Model):
    """A place (1+ regions) at a time of year, e.g. 'Marrakech Nov 2026'."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=128)
    target_date = models.DateField(null=True, blank=True)
    week_window = models.PositiveSmallIntegerField(default=1, help_text="± eBird bar-chart weeks around target_date")
    notes = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TripRegion(models.Model):
    trip_set = models.ForeignKey(TripSet, on_delete=models.CASCADE, related_name="regions")
    region_code = models.CharField(max_length=32)  # MA-07, MA-07-xx, or hotspot L123
    label = models.CharField(max_length=128, blank=True)

    class Meta:
        unique_together = [("trip_set", "region_code")]

    def __str__(self):
        return self.label or self.region_code


class Rarity(models.TextChoices):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"


def rarity_for(freq: float) -> str:
    if freq >= settings.RARITY_COMMON_MIN:
        return Rarity.COMMON
    if freq >= settings.RARITY_UNCOMMON_MIN:
        return Rarity.UNCOMMON
    return Rarity.RARE


class SpeciesFrequency(models.Model):
    trip_set = models.ForeignKey(TripSet, on_delete=models.CASCADE, related_name="frequencies")
    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="frequencies")
    frequency = models.FloatField(help_text="Fraction of checklists reporting (0-1)")
    sample_size = models.PositiveIntegerField(default=0, help_text="Checklists in window")
    rarity = models.CharField(max_length=10, choices=Rarity.choices)
    source = models.CharField(max_length=32, default="barchart")  # barchart | api_checklists | spplist
    detail = models.JSONField(default=dict, blank=True)  # raw per-region / per-week values

    class Meta:
        unique_together = [("trip_set", "taxon")]
        ordering = ["-frequency"]

    def save(self, *args, **kwargs):
        self.rarity = rarity_for(self.frequency)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.taxon.common_name} @ {self.trip_set.slug}: {self.frequency:.1%}"


class MediaType(models.TextChoices):
    PHOTO = "photo"
    AUDIO = "audio"


class MediaSource(models.TextChoices):
    FEATURED = "featured", "eBird featured (Macaulay)"
    COMMUNITY = "community", "Macaulay community"
    INATURALIST = "inaturalist", "iNaturalist"
    XENO_CANTO = "xeno_canto", "xeno-canto"


class MediaAsset(models.Model):
    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=8, choices=MediaType.choices)
    source = models.CharField(max_length=16, choices=MediaSource.choices)
    external_id = models.CharField(max_length=64, help_text="ML asset id / iNat photo id / XC id")
    source_url = models.URLField(max_length=500, blank=True)
    download_url = models.URLField(max_length=500, blank=True)
    file = models.CharField(max_length=300, blank=True, help_text="Path relative to MEDIA_ROOT")
    rating = models.FloatField(null=True, blank=True)
    contributor = models.CharField(max_length=200, blank=True)
    license = models.CharField(max_length=64, blank=True)
    location = models.CharField(max_length=300, blank=True)
    obs_date = models.DateField(null=True, blank=True)
    tags = models.JSONField(default=dict, blank=True)  # age, sex, sound_type, ...
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("source", "external_id", "media_type")]
        indexes = [models.Index(fields=["taxon", "media_type", "source"])]

    def __str__(self):
        return f"{self.get_source_display()} {self.media_type} {self.external_id} ({self.taxon.common_name})"

    @property
    def downloaded(self) -> bool:
        return bool(self.file)

    @property
    def attribution(self) -> str:
        parts = [f"© {self.contributor}" if self.contributor else ""]
        if self.source in (MediaSource.FEATURED, MediaSource.COMMUNITY):
            parts.append(f"Macaulay Library ML{self.external_id}")
        elif self.source == MediaSource.INATURALIST:
            parts.append(f"iNaturalist ({self.license})")
        elif self.source == MediaSource.XENO_CANTO:
            parts.append(f"xeno-canto XC{self.external_id} ({self.license})")
        return " · ".join(p for p in parts if p)
