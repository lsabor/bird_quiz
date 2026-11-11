"""Media sources. Each returns candidate dicts that map onto MediaAsset fields + 'ext'."""

import datetime as dt
import re

from django.conf import settings

from birds.models import MediaSource, MediaType, Taxon

from .http import PoliteClient

INAT = "https://api.inaturalist.org/v1/observations"
INAT_LICENSES = "cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nc-sa,cc-by-nd,cc-by-nc-nd"
# iNat controlled annotations
INAT_LIFE_STAGE = {2: "adult", 5: "immature", 6: "juvenile", 8: "egg"}
INAT_SEX = {10: "female", 11: "male"}


def _date(s):
    try:
        return dt.date.fromisoformat(s[:10]) if s else None
    except ValueError:
        return None


def _same_species(found: str, wanted: str) -> bool:
    """iNat lumps/splits differently from eBird; only accept the exact species or its sspp."""
    return found == wanted or found.startswith(wanted + " ")


def _inat_tags(obs) -> dict:
    tags = {}
    for a in obs.get("annotations") or []:
        if a.get("vote_score", 0) < 0:
            continue
        v = a.get("controlled_value_id")
        if a.get("controlled_attribute_id") == 1 and v in INAT_LIFE_STAGE:
            tags["age"] = INAT_LIFE_STAGE[v]
        if a.get("controlled_attribute_id") == 9 and v in INAT_SEX:
            tags["sex"] = INAT_SEX[v]
    return tags


def inaturalist(http: PoliteClient, taxon: Taxon, media_type: str, limit: int, geo: dict | None = None):
    params = {
        "taxon_name": taxon.scientific_name,
        "quality_grade": "research",
        "order_by": "votes",
        "per_page": 100,
        "page": 1,
    }
    if media_type == MediaType.PHOTO:
        params.update(photos="true", photo_license=INAT_LICENSES)
    else:
        params.update(sounds="true", sound_license=INAT_LICENSES)
    if geo:
        params.update(geo)
    out = []
    for page in range(1, 4):
        params["page"] = page
        data = http.get_json(INAT, params)
        for obs in data.get("results", []):
            if not _same_species((obs.get("taxon") or {}).get("name", ""), taxon.scientific_name):
                continue
            user = obs.get("user") or {}
            base = dict(
                taxon=taxon,
                media_type=media_type,
                source=MediaSource.INATURALIST,
                source_url=f"https://www.inaturalist.org/observations/{obs['id']}",
                contributor=user.get("name") or user.get("login", ""),
                location=obs.get("place_guess") or "",
                obs_date=_date(obs.get("observed_on")),
                rating=obs.get("faves_count"),
                tags=_inat_tags(obs),
            )
            items = obs.get("photos") if media_type == MediaType.PHOTO else obs.get("sounds")
            for m in (items or [])[:1]:  # one per observation: more variety
                if not m.get("license_code") or m.get("hidden"):
                    continue
                if media_type == MediaType.PHOTO:
                    url = m["url"].replace("/square.", "/large.")
                    ext = url.rsplit(".", 1)[-1].split("?")[0]
                else:
                    url = m["file_url"]
                    ext = url.rsplit(".", 1)[-1].split("?")[0] or "m4a"
                out.append(dict(base, external_id=str(m["id"]), download_url=url, license=m["license_code"], ext=ext))
                if len(out) >= limit:
                    return out
        if page * 100 >= data.get("total_results", 0):
            break
    return out


XC = "https://xeno-canto.org/api/3/recordings"


def _xc_seconds(length: str) -> int:
    parts = [int(p) for p in re.findall(r"\d+", length or "")] or [9999]
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def _xc_license(url: str) -> str:
    m = re.search(r"licenses/([a-z-]+)/", url or "")
    return f"cc-{m[1]}" if m else (url or "")


def xeno_canto(http: PoliteClient, taxon: Taxon, limit: int, max_seconds: int = 60, box: str | None = None):
    """box = 'lat_min,lon_min,lat_max,lon_max': prefer recordings there, then top up from anywhere."""
    if not settings.XENO_CANTO_API_KEY:
        raise RuntimeError("XENO_CANTO_API_KEY is not set in .env (free: https://xeno-canto.org/account)")
    genus, _, epithet = taxon.scientific_name.partition(" ")
    out, seen = [], set()
    passes = [(box, q) for q in ("A", "B")] if box else []
    passes += [(None, q) for q in ("A", "B")]
    for area, quality in passes:
        query = f"gen:{genus} sp:{epithet} q:{quality}" + (f" box:{area}" if area else "")
        data = http.get_json(XC, {"query": query, "key": settings.XENO_CANTO_API_KEY, "per_page": 100})
        for r in data.get("recordings", []):
            if _xc_seconds(r.get("length")) > max_seconds or str(r["id"]) in seen:
                continue
            seen.add(str(r["id"]))
            tags = {"sound_type": (r.get("type") or "").lower()}
            for key, field in (("sex", "sex"), ("age", "stage")):
                val = (r.get(field) or "").lower()
                if val and val != "uncertain":
                    tags[key] = val
            file_url = r["file"] if r["file"].startswith("http") else "https:" + r["file"]
            out.append(
                dict(
                    taxon=taxon,
                    media_type=MediaType.AUDIO,
                    source=MediaSource.XENO_CANTO,
                    external_id=str(r["id"]),
                    source_url=f"https://xeno-canto.org/{r['id']}",
                    download_url=file_url,
                    contributor=r.get("rec", ""),
                    license=_xc_license(r.get("lic")),
                    location=", ".join(x for x in (r.get("loc"), r.get("cnt")) if x),
                    obs_date=_date(r.get("date")),
                    rating={"A": 5, "B": 4}[quality],
                    tags=tags,
                    ext="mp3",
                )
            )
            if len(out) >= limit:
                return out
    return out
