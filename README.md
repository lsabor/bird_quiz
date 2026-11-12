# bird_quiz

An offline, more flexible take on the [eBird Quiz](https://ebird.org/quiz/). You build a species list
for a specific place and time of year, download photos and audio for those birds once, and then
quiz yourself locally. You can filter by media type, source and rarity.

See [DEVELOPMENT.md](DEVELOPMENT.md) for the design, status and roadmap.

## Setup

Requires Python 3.12, [uv](https://docs.astral.sh/uv/) and a local Postgres server.

```bash
uv sync
createdb bird_quiz
cp .env.example .env          # add your EBIRD_API_KEY (https://ebird.org/api/keygen)
uv run python manage.py migrate
uv run python manage.py sync_taxonomy
```

## Build a trip

```bash
# 1. Find region / hotspot codes
uv run python manage.py find_regions --country MA          # subnational1 regions
uv run python manage.py find_regions --near 31.63,-8.00    # hotspots near a lat,lng

# 2. Create the trip. Each --region is a location (region or hotspot); re-run to add more.
uv run python manage.py create_trip marrakech-2026-11 --name "Marrakech Nov 2026" \
    --date 2026-11-20 --window 1 --region "MA-11=Marrakech-Tensift-Al Haouz" \
    --region "L13476308=Oukaïmeden (upper pine forest)"

# 3. Species + likelihood, per location — either:
#   a) best: eBird bar chart. While logged in, open
#      https://ebird.org/barchart?r=<CODE>&bmo=1&emo=12&byr=1900&eyr=2026 -> "Download Histogram Data", then:
uv run python manage.py import_barchart marrakech-2026-11 MA-11=path/to/downloaded_barchart.txt
#   b) or no login: sample real checklists via the API (a few minutes per location)
uv run python manage.py estimate_frequency marrakech-2026-11 --region L13476308 --years 12

# 4. Media for every species at any of the trip's locations (resumable; already-downloaded media is skipped)
uv run python manage.py fetch_media marrakech-2026-11 --photos 15 --audio 10
#   --sources inaturalist,xeno_canto   (xeno-canto needs XENO_CANTO_API_KEY)
#   --inat-near 31.6,-8.0,1500         (prefer media from nearby, for regional plumages)
```

## Quiz

```bash
uv run python manage.py runserver
# open http://localhost:8000
```

Tick one or more of the trip's locations on the setup page. When several are combined, each bird gets its
frequency (and rarity) from the location where it is most common.

Keyboard shortcuts: `1`–`9` pick an answer, `0`/`o` picks "Other", `space` plays or pauses audio, and
`Enter` moves to the next question. The admin at `/admin/` (create a user with `createsuperuser`) is
handy for browsing data.

## Sharing / backup

```bash
uv run python manage.py export_pack marrakech-2026-11            # -> packs/marrakech-2026-11.tar.gz
uv run python manage.py import_pack packs/marrakech-2026-11.tar.gz
# full backup: pg_dump -Fc bird_quiz > bird_quiz.dump && tar czf media.tgz media/
```

## Media licensing

This repo contains code only. Downloaded media, the database and packs are gitignored. Each media
file belongs to its contributor and keeps its attribution and license, which the quiz displays. The
current sources (iNaturalist and xeno-canto) are Creative Commons licensed. Most of those licenses are
NonCommercial and require attribution, so share packs privately and non-commercially.
