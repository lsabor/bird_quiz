import pytest

from birds.models import MediaAsset, SpeciesFrequency, Taxon, TripSet
from quiz.engine import QuizSettings, build_quiz
from quiz.models import OTHER


@pytest.fixture
def trip(db):
    trip = TripSet.objects.create(slug="t", name="T")
    for i in range(8):
        tx = Taxon.objects.create(
            species_code=f"sp{i}",
            common_name=f"Bird {i}",
            scientific_name=f"Genus{i % 3} sp{i}",
            category="species",
            taxon_order=i,
            family_code=f"fam{i % 2}",
            order="Ord",
        )
        SpeciesFrequency(trip_set=trip, taxon=tx, frequency=[0.5, 0.05, 0.01][i % 3]).save()
        if i < 6:
            MediaAsset.objects.create(
                taxon=tx, media_type="photo", source="inaturalist", external_id=f"p{i}", file=f"sp{i}/a.jpg"
            )
            MediaAsset.objects.create(
                taxon=tx, media_type="audio", source="xeno_canto", external_id=f"a{i}", file=f"sp{i}/a.mp3"
            )
    return trip


def test_build_basic(trip):
    s = build_quiz(QuizSettings(trip="t", n_questions=10, n_options=4, other_rate=0, seed=1))
    answers = list(s.answers.all())
    assert len(answers) == 10
    for a in answers:
        assert len(a.options) == 4 and len(set(a.options)) == 4
        assert a.correct_choice == a.taxon.species_code in a.options
    # all 6 species with media get used before any repeat
    assert len({a.taxon_id for a in answers[:6]}) == 6


def test_filters_and_other(trip):
    s = build_quiz(
        QuizSettings(trip="t", n_questions=12, media_types=["audio"], rarities=["common"], other_rate=1.0, seed=2)
    )
    for a in s.answers.all():
        assert a.asset.media_type == "audio"
        assert a.taxon.frequencies.get().rarity == "common"
        assert a.correct_choice == OTHER and a.taxon.species_code not in a.options


def test_no_match(trip):
    with pytest.raises(ValueError):
        build_quiz(QuizSettings(trip="t", sources=["featured"]))


def test_flow(client, trip):
    r = client.post("/", {"trip": "t", "n_questions": 3, "media_types": ["photo"], "n_options": 3, "other_rate": 0})
    assert r.status_code == 302
    url = r["Location"]
    assert client.get(url).status_code == 200
    from quiz.models import QuizSession

    sess = QuizSession.objects.get()
    for a in sess.answers.all():
        client.post(f"/q/{sess.pk}/{a.index}/answer/", {"choice": a.correct_choice, "response_ms": "1234"})
    sess.refresh_from_db()
    assert sess.finished and sess.score == (3, 3, 3)
    page = client.get(f"/q/{sess.pk}/0/").content.decode()
    assert "Correct" in page
    assert client.get(f"/q/{sess.pk}/results/").status_code == 200
    # miss one and re-quiz
    r = client.post("/", {"trip": "t", "n_questions": 2, "media_types": ["photo"]})
    s2 = QuizSession.objects.first()
    a = s2.answers.first()
    client.post(f"/q/{s2.pk}/{a.index}/answer/", {"choice": OTHER if a.correct_choice != OTHER else a.options[0]})
    r = client.post(f"/q/{s2.pk}/requiz/", {"species": a.taxon.species_code})
    s3 = QuizSession.objects.first()
    assert {x.taxon_id for x in s3.answers.all()} == {a.taxon_id}
