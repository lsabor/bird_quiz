from django.contrib import admin

from .models import MediaAsset, SpeciesFrequency, Taxon, TripRegion, TripSet


@admin.register(Taxon)
class TaxonAdmin(admin.ModelAdmin):
    list_display = ["common_name", "scientific_name", "species_code", "family_common", "category"]
    list_filter = ["category"]
    search_fields = ["common_name", "scientific_name", "species_code"]


class TripRegionInline(admin.TabularInline):
    model = TripRegion
    extra = 0


@admin.register(TripSet)
class TripSetAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "target_date", "week_window"]
    inlines = [TripRegionInline]


@admin.register(SpeciesFrequency)
class SpeciesFrequencyAdmin(admin.ModelAdmin):
    list_display = ["taxon", "region", "frequency", "rarity", "sample_size", "source"]
    list_filter = ["region__trip_set", "region", "rarity", "source"]
    search_fields = ["taxon__common_name"]
    raw_id_fields = ["taxon"]


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["taxon", "media_type", "source", "external_id", "contributor", "rating", "downloaded"]
    list_filter = ["media_type", "source"]
    search_fields = ["taxon__common_name", "external_id", "contributor"]
    raw_id_fields = ["taxon"]
