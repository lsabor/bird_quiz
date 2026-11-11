"""Question generation."""

import random
from dataclasses import asdict, dataclass, field

from birds.models import MediaAsset, MediaSource, SpeciesFrequency, TripSet

from .models import OTHER, QuizAnswer, QuizSession

MACAULAY = [MediaSource.FEATURED, MediaSource.COMMUNITY]


@dataclass
class QuizSettings:
    trip: str
    n_questions: int = 20
    media_types: list[str] = field(default_factory=lambda: ["photo", "audio"])
    sources: list[str] = field(default_factory=lambda: ["featured", "community", "inaturalist", "xeno_canto"])
    rarities: list[str] = field(default_factory=lambda: ["common", "uncommon", "rare"])
    n_options: int = 5
    other_rate: float = 0.1  # chance the right answer is hidden and "Other" is correct
    distractors: str = "family"  # random | family
    weighting: str = "uniform"  # uniform | frequency
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
    freqs = SpeciesFrequency.objects.filter(trip_set=trip).select_related("taxon")
    all_trip_taxa = [f.taxon for f in freqs]  # distractors may come from any trip species
    target = freqs.filter(rarity__in=s.rarities)
    if s.species:
        target = target.filter(taxon__species_code__in=s.species)

    assets = MediaAsset.objects.filter(
        taxon__in=[f.taxon for f in target],
        media_type__in=s.media_types,
        source__in=s.sources,
    ).exclude(file="")
    by_taxon: dict[int, list[MediaAsset]] = {}
    for a in assets:
        by_taxon.setdefault(a.taxon_id, []).append(a)
    candidates = [f for f in target if f.taxon_id in by_taxon]
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
        lst = by_taxon[f.taxon_id]
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
