"""Question generation."""

import random
from dataclasses import asdict, dataclass, field

from django.db.models import Q

from birds.models import MediaAsset, MediaSource, TripSet, combined_frequencies

from .models import OTHER, QuizAnswer, QuizSession

MACAULAY = [MediaSource.FEATURED, MediaSource.COMMUNITY]
AUDIO_MIN_RATING = {"rated": 4, "best": 5}


@dataclass
class QuizSettings:
    trip: str
    regions: list[str] = field(default_factory=list)  # trip location codes to combine; empty = all
    n_questions: int = 20
    media_types: list[str] = field(default_factory=lambda: ["photo", "audio"])
    sources: list[str] = field(default_factory=lambda: ["featured", "community", "inaturalist", "xeno_canto"])
    rarities: list[str] = field(default_factory=lambda: ["common", "uncommon", "rare"])
    n_options: int = 5
    other_rate: float = 0.1  # chance the right answer is hidden and "Other" is correct
    distractors: str = "family"  # random | family
    weighting: str = "uniform"  # uniform | frequency
    audio_quality: str = "any"  # any | rated (xeno-canto A/B only) | best (xeno-canto A only)
    species: list[str] = field(default_factory=list)  # optional explicit species subset (e.g. re-quiz misses)
    seed: int | None = None


def _distractor_pool(correct, pool, mode, rng):
    others = [t for t in pool if t.pk != correct.pk]
    rng.shuffle(others)
    if mode != "family":
        return others

    def closeness(t):
        if t.genus == correct.genus:
            return 0
        if t.family_code == correct.family_code:
            return 1
        if t.order == correct.order:
            return 2
        return 3

    # Mostly near relatives, with a bit of randomness so it isn't always the same set
    return sorted(others, key=lambda t: closeness(t) + rng.random() * 1.5)


def build_quiz(s: QuizSettings) -> QuizSession:
    rng = random.Random(s.seed)
    trip = TripSet.objects.get(slug=s.trip)
    # Combine the chosen locations; a species takes its frequency (and rarity) from where it's most common.
    combined = combined_frequencies(trip, s.regions)
    all_trip_taxa = [c.taxon for c in combined.values()]  # distractors may come from any of those species
    target = [c for c in combined.values() if c.rarity in s.rarities]
    if s.species:
        target = [c for c in target if c.taxon.species_code in s.species]

    assets = (
        MediaAsset.objects.filter(
            taxon__in=[c.taxon for c in target],
            media_type__in=s.media_types,
            source__in=s.sources,
        )
        .exclude(file="")
        .exclude(excluded=True)
    )
    if s.audio_quality in AUDIO_MIN_RATING:
        # iNaturalist audio has no quality signal; xeno-canto ratings: A=5, B=4
        assets = assets.exclude(
            Q(media_type="audio") & ~Q(source="xeno_canto", rating__gte=AUDIO_MIN_RATING[s.audio_quality])
        )
    by_taxon: dict[int, list[MediaAsset]] = {}
    for a in assets:
        by_taxon.setdefault(a.taxon_id, []).append(a)
    candidates = [c for c in target if c.taxon.pk in by_taxon]
    if not candidates:
        raise ValueError("No species match those filters (or no media has been downloaded for them).")

    # Draw species without replacement (refilling when exhausted), then an unused asset for each.
    picks, bag = [], []
    for _ in range(s.n_questions):
        if not bag:
            bag = list(candidates)
            if s.weighting == "frequency":
                # weighted shuffle (Efraimidis-Spirakis)
                bag.sort(key=lambda f: rng.random() ** (1 / max(f.frequency, 1e-4)), reverse=True)
            else:
                rng.shuffle(bag)
            bag.reverse()
        picks.append(bag.pop())
    for lst in by_taxon.values():
        rng.shuffle(lst)

    session = QuizSession.objects.create(trip_set=trip, settings=asdict(s))
    answers = []
    for i, f in enumerate(picks):
        lst = by_taxon[f.taxon.pk]
        asset = lst.pop(0)
        lst.append(asset)  # rotate
        hide = rng.random() < s.other_rate
        n_distractors = s.n_options if hide else s.n_options - 1
        options = _distractor_pool(f.taxon, all_trip_taxa, s.distractors, rng)[:n_distractors]
        if not hide:
            options.append(f.taxon)
        rng.shuffle(options)
        answers.append(
            QuizAnswer(
                session=session,
                index=i,
                asset=asset,
                taxon=f.taxon,
                options=[t.species_code for t in options],
                correct_choice=OTHER if hide else f.taxon.species_code,
            )
        )
    QuizAnswer.objects.bulk_create(answers)
    return session
