"""Minimal eBird API 2.0 client (https://documenter.getpostman.com/view/664302/S1ENwy59)."""

from django.conf import settings

from .http import PoliteClient

BASE = "https://api.ebird.org/v2"


class EbirdApi:
    def __init__(self, refresh: bool = False, delay: float | None = None):
        headers = {"X-eBirdApiToken": settings.EBIRD_API_KEY} if settings.EBIRD_API_KEY else {}
        self.http = PoliteClient(headers=headers, refresh=refresh, delay=delay)

    def require_key(self):
        if not settings.EBIRD_API_KEY:
            raise RuntimeError("EBIRD_API_KEY is not set in .env (get one at https://ebird.org/api/keygen)")

    def taxonomy(self):
        return self.http.get_json(f"{BASE}/ref/taxonomy/ebird", {"fmt": "json"})

    def region_info(self, code: str):
        self.require_key()
        return self.http.get_json(f"{BASE}/ref/region/info/{code}")

    def subregions(self, region_type: str, parent: str):
        self.require_key()
        return self.http.get_json(f"{BASE}/ref/region/list/{region_type}/{parent}")

    def hotspots_near(self, lat: float, lng: float, dist_km: int = 25):
        self.require_key()
        return self.http.get_json(f"{BASE}/ref/hotspot/geo", {"lat": lat, "lng": lng, "dist": dist_km, "fmt": "json"})

    def species_list(self, region: str) -> list[str]:
        self.require_key()
        return self.http.get_json(f"{BASE}/product/spplist/{region}")

    def checklists_on(self, region: str, y: int, m: int, d: int):
        self.require_key()
        return self.http.get_json(f"{BASE}/product/lists/{region}/{y}/{m}/{d}", {"maxResults": 200})

    def checklist(self, sub_id: str):
        self.require_key()
        return self.http.get_json(f"{BASE}/product/checklist/view/{sub_id}")
