"""Shared polite HTTP client: rate limiting + on-disk cache of raw responses."""

import hashlib
import json
import time
from pathlib import Path

import httpx
from django.conf import settings


class PoliteClient:
    def __init__(self, delay: float | None = None, headers: dict | None = None, refresh: bool = False):
        self.delay = settings.SCRAPE_DELAY_SECONDS if delay is None else delay
        self.refresh = refresh
        self.cache_dir = Path(settings.DATA_DIR) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last = 0.0
        self.client = httpx.Client(
            headers={"User-Agent": settings.SCRAPE_USER_AGENT, **(headers or {})},
            timeout=60,
            follow_redirects=True,
        )

    def _wait(self):
        dt = time.monotonic() - self._last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self._last = time.monotonic()

    def _cache_path(self, url: str, params: dict | None) -> Path:
        key = url + "?" + json.dumps(params or {}, sort_keys=True)
        h = hashlib.sha256(key.encode()).hexdigest()[:24]
        return self.cache_dir / h[:2] / f"{h}.json"

    def get_json(self, url: str, params: dict | None = None, cache: bool = True):
        path = self._cache_path(url, params)
        if cache and not self.refresh and path.exists():
            return json.loads(path.read_text())
        for attempt in range(4):
            self._wait()
            r = self.client.get(url, params=params)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            r.raise_for_status()
        data = r.json()
        if cache:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        return data

    def download(self, url: str, dest: Path) -> Path:
        """Download a binary to dest (skips if it already exists)."""
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._wait()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with self.client.stream("GET", url) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
        tmp.rename(dest)
        return dest
