# bird_quiz — Development Plan

A more flexible, offline-capable clone of the [eBird Quiz](https://ebird.org/quiz/).
Pull the species likely at a specific place and time (e.g. Marrakech, 20 Nov),
download their media once, then run quizzes locally with filters.

This document is the source of truth for picking work back up. Update the
**Status** section as phases land.

---

## Status

| Phase | Description | State |
|---|---|---|
| 0 | Project scaffolding (Django, Postgres, .env, uv) | done |
| 1 | Taxonomy + region species/frequency | done: `sync_taxonomy`, `find_regions`, `create_trip`, `import_barchart` (manual TSV), `estimate_frequency` (API) |
| 2 | Media | iNaturalist + xeno-canto done (`fetch_media`); **Macaulay blocked, see below** |
| 3 | Quiz app (setup → questions → results) | done (untested in a real browser so far) |
| 4 | Export/import "packs" for hand-off | done (`export_pack` / `import_pack`, .tar.gz) |
| 5 | Performance tracking & progression views | later (answers + response times already recorded) |

### Findings from probing endpoints (2026-11-10)
- The **eBird API** works as expected. Taxonomy needs no key; everything else uses `EBIRD_API_KEY`.
- **Marrakech = `MA-11`** (Marrakech-Tensift-Al Haouz). eBird still uses the pre-2015 Moroccan
  regions and has no subnational2 under MA-11. Hotspots near the city come from
  `find_regions --near 31.63,-8.00`.
- The **bar chart TSV** (`ebird.org/barchartData`) redirects to the Cornell login (CAS).
  - We do **not** automate login. You download the TSV by hand (one click while logged in), and
    `import_barchart` parses it.
  - `estimate_frequency` is a no-login alternative. It samples real checklists through
    `/v2/product/lists/{region}/{y}/{m}/{d}` and `/v2/product/checklist/view/{subId}`, and counts
    only complete checklists (`allObsReported`).
- **Macaulay Library search API and ebird.org species pages sit behind an "Anubis" anti-bot
  challenge.** Automating around that counts as bot-check circumvention, so **we don't do it.** The
  ML CDN (`cdn.download.ams.birds.cornell.edu/api/v1/asset/<id>/<size>`) is *not* gated, but asset
  IDs are only discoverable through the gated pages. Options still open (owner's decision):
  1. Stick with iNaturalist + xeno-canto. Both have official APIs and CC licenses, so packs can be
     shared non-commercially with attribution.
  2. Add a manual-curation path: you browse ML/eBird yourself and paste asset IDs (e.g.
     `ML123456`) into a command that downloads them from the CDN.
  3. Ask Cornell for ML API / data access (they have a research-request process).
- **iNaturalist taxonomy differs from eBird's.** For example, iNat lumps Black-necked Stilt into
  *Himantopus himantopus*. `sources._same_species` rejects observations whose iNat taxon isn't
  exactly the eBird species (or one of its subspecies).
- `fetch_media --inat-near lat,lng,km` biases iNat results geographically, for regional plumages and
  subspecies.
- **Spectrogram gotchas** (`quiz/static/quiz/quiz.js`):
  - wavesurfer decodes at 8 kHz by default, which caps the spectrogram at 4 kHz. We decode at 22.05 kHz.
  - The plugin's default mel scale limits the canvas height to `fftSamples/8` px. We use `scale: "linear"`.
  - The plugin works in absolute dB, so quiet recordings render blank. The page decodes the clip,
    peak-normalizes it and loads it as a WAV blob. The colormap is grayscale on white, Macaulay-style.
- **Real bar chart TSVs use plain eBird common names** as labels (no scientific names), and include
  spuh/slash/hybrid rows. `import_barchart` matches on common name and drops non-species rows by
  default.
- **Marrakech trip** (`marrakech-2026-11`) has two locations:
  - `MA-11`: bar chart import, 467 checklists in Nov wk 2–4, 216 species. The earlier API sample
    found 153.
  - `L13476308` (Oukaïmeden upper pine forest): bar chart imported with `--window 2`, giving
    15 checklists and 45 species. It's sparse in November (only 9 checklists at ±1 week).
- **Media quality signals:**
  - **xeno-canto:** community A–E grades are meaningful. We fetch only A and B (stored rating 5/4).
  - **iNaturalist:** the rating is the observation's favorites count, which is almost always 0–1, so
    it's useless as a quality signal.
  - **What the quiz offers:**
    - an "Audio quality" setting: any / xeno-canto A–B / xeno-canto A only
    - a per-media "👎 never show again" flag (`MediaAsset.excluded`, shortcut `x`), which travels
      in packs
  - **Possible later:** an automatic audio SNR score, which needs ffmpeg to decode m4a/mp3; and
    storing photo resolution to filter out small originals.
- **Headless Chromium** for UI screenshots needs system libraries:
  `sudo .venv/bin/playwright install-deps chromium`.

**Near-term deadline:** Marrakech trip, birding 2026-11-20. Phases 0–3 must be
usable before then; 4–5 can follow.

---

## Terms of use / what goes public

Short version: **the code can be public; the data must stay private.**

- **eBird API 2.0** (taxonomy, region lists, hotspots) is free with a personal
  API key and allowed for non-commercial use with attribution. Low risk.
- **Bar chart (frequency) data** comes from the logged-in "Download histogram
  data" endpoint on ebird.org, not the official API. Fetching it for your own
  trips at a polite rate is what the website does for you anyway. Low risk, but
  it is still automated use of the site, so keep it rate-limited.
- **Macaulay Library media** (the photos/audio on species pages) is copyrighted
  by each contributor. ML's terms allow viewing for personal use. They do **not**
  allow redistributing it. Downloading a few hundred assets for private study is
  a gray area. The realistic worst case is an account warning or ban, not legal
  trouble, as long as the media is never republished.
- Therefore:
  - The repo contains **code only**. `media/`, `data/`, `packs/`, DB dumps and the
    browser profile are gitignored.
  - Every media row stores its ML asset ID, contributor name and license. The quiz
    shows "© contributor / Macaulay Library MLxxxx" on each question.
  - Packs (Phase 4) are for **private** hand-off to friends. Never post them publicly.
  - Scrapers sleep about 1 s between requests and cache every raw response, so
    nothing is fetched twice.
- Optional, cleaner audio source for the future: **xeno-canto** (API v3, key
  required, most recordings CC-licensed). It could be added as a third media
  source, and some of its recordings could legitimately be redistributed.

---

## Tech stack

- **Python 3.12**, managed with **uv** (`pyproject.toml`, `uv.lock`).
- **Django 5.2** + **Postgres 16** (already running locally) via `dj-database-url`.
- **python-dotenv** for `.env`. Commit `.env.example` and never `.env`.
- **httpx** for API/JSON calls. **Playwright** (Chromium) only to obtain a
  logged-in eBird session.
- **Frontend:** Django templates + a little vanilla JS. No Next.js.
  **wavesurfer.js** + its spectrogram plugin are *vendored* into `static/` so the
  quiz works fully offline (no CDN).
- Media files live on disk under `MEDIA_ROOT` (`./media/`). The DB stores paths
  and metadata only, so dumps stay small and portable.

### `.env` keys
```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=1
DATABASE_URL=postgres://<user>:<pass>@localhost:5432/bird_quiz
EBIRD_API_KEY=            # https://ebird.org/api/keygen
SCRAPE_DELAY_SECONDS=1.0
BROWSER_PROFILE_DIR=.browser-profile
```
No eBird password is stored. You log in by hand once in the Playwright window and
the persistent profile keeps the session.

---

## Repo layout (target)

```
bird_quiz/
  DEVELOPMENT.md  README.md  pyproject.toml  .env.example  manage.py
  config/                 # Django settings/urls/wsgi
  birds/                  # core data models: Taxon, TripSet, SpeciesFrequency, MediaAsset
  scraper/                # clients + management commands
    ebird_api.py          # official API 2.0 client
    session.py            # Playwright login -> cookies -> httpx client
    barchart.py           # histogram TSV fetch + parse
    macaulay.py           # ML search + asset download
    cache.py              # raw-response disk cache (data/cache/)
    management/commands/  # ebird_login, sync_taxonomy, scrape_region, scrape_media, export_pack, import_pack
  quiz/                   # quiz models, views, templates, static (vendored wavesurfer)
  media/   data/   packs/ # gitignored
```

---

## Data model (sketch)

```
Taxon
  species_code (PK-ish, e.g. "bkwsti"), common_name, scientific_name,
  family_common, family_scientific, order, taxon_order, category (species/issf/…)

TripSet                       # "Marrakech Nov 2026"
  slug, name, target_date, week_window (±N bar-chart weeks), notes

TripRegion                    # 1..n regions/hotspots per trip
  trip_set FK, region_code ("MA-07", "MA-07-xxx", or hotspot "L123456"), label

SpeciesFrequency               # one row per LOCATION (TripRegion) x species
  region FK, taxon FK, frequency (0–1, sample-size-weighted over the window's weeks),
  sample_size (checklists), source (barchart | api_checklists), detail JSON (per-week values)
  rarity (derived: common / uncommon / rare, thresholds in settings)
  -> birds.models.combined_frequencies(trip, region_codes) merges the chosen locations: a species
     takes the frequency/rarity of the location where it is most common. Media is per species, so
     adding a location only downloads media for species that are new.

MediaAsset
  ml_asset_id (unique), taxon FK, media_type (photo/audio),
  source (featured | community | xeno_canto),
  rating, contributor, license, location, obs_date,
  tags JSON (age, sex, sound type: song/call/…), 
  file (local path), spectrogram_file (optional), width/height/duration

QuizSession                   # Phase 3; recorded from day one (cheap)
  created, settings JSON (trip, n_questions, media types, sources, rarity, …)
QuizAnswer
  session FK, asset FK, correct_taxon FK, options JSON, chosen (taxon or "other"),
  is_correct, response_ms
```

---

## Phase 0: Scaffolding
1. `uv init`. Add django, psycopg[binary], dj-database-url, python-dotenv, httpx,
   playwright, pytest-django, ruff.
2. Create the `config` project and the `birds`, `scraper` and `quiz` apps. Settings
   read from `.env`.
3. `createdb bird_quiz`. Add `.env.example`. Extend `.gitignore` with `media/`,
   `data/`, `packs/`, `.browser-profile/`, `*.dump`.
4. Expose the Django admin for all models. This gives free data inspection and
   cleanup.

## Phase 1: Species list + likelihood
1. **`sync_taxonomy`**: `GET /v2/ref/taxonomy/ebird?fmt=json` loads the whole
   taxonomy (~17k rows) into `Taxon`, including family and order, which later
   drive smart distractors.
2. **Region resolution helper**: `/v2/ref/region/list/subnational1/MA` and
   `/subnational2/...`, plus `/v2/ref/hotspot/geo?lat=&lng=` to pick hotspots.
   Marrakech is `MA-11` (confirmed, see Findings).
3. **`ebird_login`**: opens headed Chromium with a persistent profile. You log in,
   then press Enter. Cookies persist in `.browser-profile/`. `session.py` loads
   them into an `httpx.Client` for later requests, so Playwright isn't needed per
   request.
4. **`scrape_region --trip marrakech-2026-11 --region MA-07 [--region L…] --date 2026-11-20 --window 1`**
   - Fetches bar chart TSV: `https://ebird.org/barchartData?r=<code>&bmo=1&emo=12&byr=1900&eyr=<year>&fmt=tsv`
     (**endpoint to verify**: it's what the "Download Histogram Data" link uses).
   - eBird splits each month into 4 "weeks" (1–7, 8–14, 15–21, 22–end).
     20 Nov = Nov wk 3. With `--window 1` we use Nov wk 2–4.
   - Stores frequency (fraction of checklists reporting the species) and sample
     size. Combines multiple regions with max (configurable).
   - Fallback when not logged in: `/v2/product/spplist/<region>` gives presence
     only, with no likelihood.
   - Drops non-species rows (spuh, slash) by default, with a flag to keep them.
5. Rarity buckets (defaults, tunable): **common** ≥ 10%, **uncommon** 2–10%,
   **rare** < 2%.

## Phase 2: Media
Media comes from the **Macaulay Library search API** (the JSON endpoint behind
ML/eBird pages), which avoids parsing HTML:
`https://search.macaulaylibrary.org/api/v1/search?taxonCode=<code>&mediaType=photo|audio&sort=rating_rank_desc&count=N`
(**verify the exact params and whether auth cookies are needed**).

1. **Featured ("default") media**: the assets shown on `ebird.org/species/<code>`.
   Get their asset IDs from the species page (one HTML fetch, then parse the
   embedded asset IDs or JSON), or failing that the top-N by rating. Tagged
   `source=featured`.
2. **Community media**: further results from the same search, paged and
   optionally filtered by minimum rating. Tagged `source=community`. Default
   counts: 10 photos and 5 audio featured, 20 photos and 10 audio community, all
   configurable.
3. Download assets from
   `https://cdn.download.ams.birds.cornell.edu/api/v1/asset/<id>/<size>` (photos
   at 1200 px; audio as mp3, **verify path**). Grab ML's pre-rendered spectrogram
   image where available; otherwise wavesurfer renders it client-side.
4. Keep ML metadata (age/sex/sound-type tags, location, date, rating) for quiz
   filters.
5. **`scrape_media --trip marrakech-2026-11 [--photos 10 --audio 5 --community-photos 20 --community-audio 10] [--only-missing]`**.
   Idempotent and resumable: it skips assets already on disk, so it's safe to
   Ctrl-C and rerun.
6. Rough scale: about 250 species × about 45 assets ≈ 11k files. Photos ~200 KB
   and audio ~1 MB come to roughly 3–5 GB. At 1 req/s that's ~3 h, so it runs
   overnight.

## Phase 3: Quiz app
- `/` **setup form**:
  - trip set
  - number of questions
  - media: photo / audio / both
  - include community media (toggle)
  - rarity: common / uncommon / rare (multi-select)
  - number of options (default 5)
  - "Other" frequency (% of questions where the correct answer isn't listed)
  - distractor mode: random / same family / similar frequency
  - extra filters (later): age/sex tags, song vs call
- **Question page**:
  - photo shown large, *or* audio with a playable, seekable wavesurfer spectrogram
  - N options plus **"Other / not listed"**
  - keyboard shortcuts (1–9, space to play audio)
  - immediate feedback: correct species, scientific name, frequency at the trip
    location, and attribution
- **Sampling**: draw a species first (uniformly, or weighted by frequency as an
  option), then pick one of its assets that matches the filters. This stops
  species with lots of media from dominating.
- **Distractors**: drawn from the same trip set, preferring the same family/genus
  when that mode is on, so the choices are actually hard.
- **"Other" semantics**: with probability p the correct species is left out of
  the options, and "Other" becomes the correct answer.
- **Results page**: score, list of misses with media to review, and a "re-quiz
  misses" button.
- Every answer is saved to `QuizAnswer` from the start, so Phase 5 is just views.

## Phase 4: Hand-off packs
DB-agnostic export, so a friend doesn't need Postgres or a matching schema version:
- **`export_pack --trip marrakech-2026-11 --out packs/marrakech.tar.zst`** writes
  `manifest.json` (taxa, frequencies, asset metadata) and the `media/` files.
- **`import_pack packs/marrakech.tar.zst`** upserts by `species_code` /
  `ml_asset_id`.
- `pg_dump -Fc bird_quiz > bird_quiz.dump` plus `tar media/` remains the quick
  full-backup path. It's documented in the README.

## Phase 5: Progress tracking (later)
- Per-species accuracy and confusion pairs ("you call Spotless Starling
  'Common Starling' 40% of the time").
- Accuracy over time per trip set.
- Spaced-repetition-style sampling that favours weak species.

---

## Open questions / to verify early
1. Exact bar chart TSV endpoint and format. Does it need login?
2. ML search API params, page size, auth requirement, and audio download path.
3. How featured species-page media IDs are exposed (embedded JSON vs separate
   call).
4. Region code(s) for Marrakech. Region-wide vs specific hotspots (likely both:
   a city hotspot plus the surrounding subnational region).

## Working conventions
- Scrapers: one shared rate-limited client, raw responses cached under
  `data/cache/`, and no fetch is repeated unless `--refresh` is passed.
- Tests: pytest-django. Parser tests use saved fixture files, never live network
  calls.
- Lint: ruff.
