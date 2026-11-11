from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from birds.models import MediaAsset, MediaSource, Rarity, Taxon, TripSet

from .engine import QuizSettings, build_quiz
from .models import OTHER, QuizAnswer, QuizSession


def setup(request):
    trips = TripSet.objects.annotate(n_species=Count("frequencies")).order_by("-created")
    if request.method == "POST":
        p = request.POST
        s = QuizSettings(
            trip=p["trip"],
            n_questions=max(1, min(500, int(p.get("n_questions", 20)))),
            media_types=p.getlist("media_types") or ["photo"],
            sources=p.getlist("sources") or [c for c, _ in MediaSource.choices],
            rarities=p.getlist("rarities") or [c for c, _ in Rarity.choices],
            n_options=max(2, min(12, int(p.get("n_options", 5)))),
            other_rate=max(0.0, min(0.9, float(p.get("other_rate", 10)) / 100)),
            distractors=p.get("distractors", "family"),
            weighting=p.get("weighting", "uniform"),
            species=[c for c in p.get("species", "").split(",") if c],
        )
        request.session["last_settings"] = {k: v for k, v in s.__dict__.items() if k != "species"}
        try:
            session = build_quiz(s)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("quiz:setup")
        return redirect("quiz:question", session.pk, 0)

    last = request.session.get("last_settings") or QuizSettings(trip="").__dict__
    trip_stats = []
    for t in trips:
        counts = (
            MediaAsset.objects.filter(taxon__frequencies__trip_set=t)
            .exclude(file="")
            .aggregate(
                photos=Count("id", filter=Q(media_type="photo")), audio=Count("id", filter=Q(media_type="audio"))
            )
        )
        trip_stats.append((t, counts))
    return render(
        request,
        "quiz/setup.html",
        {
            "trip_stats": trip_stats,
            "last": last,
            "sources": MediaSource.choices,
            "rarities": Rarity.choices,
            "recent": QuizSession.objects.select_related("trip_set")[:10],
        },
    )


def _taxa(codes):
    by_code = {t.species_code: t for t in Taxon.objects.filter(species_code__in=codes)}
    return [by_code[c] for c in codes if c in by_code]


def question(request, session_id, index):
    session = get_object_or_404(QuizSession, pk=session_id)
    ans = get_object_or_404(QuizAnswer.objects.select_related("asset", "taxon"), session=session, index=index)
    total = session.answers.count()
    freq = ans.taxon.frequencies.filter(trip_set=session.trip_set).first()
    correct, answered, _ = session.score
    return render(
        request,
        "quiz/question.html",
        {
            "session": session,
            "ans": ans,
            "options": _taxa(ans.options),
            "OTHER": OTHER,
            "total": total,
            "number": index + 1,
            "is_last": index + 1 >= total,
            "freq": freq,
            "chosen_taxon": Taxon.objects.filter(species_code=ans.chosen).first() if ans.chosen else None,
            "correct_so_far": correct,
            "answered_so_far": answered,
        },
    )


@require_POST
def answer(request, session_id, index):
    ans = get_object_or_404(QuizAnswer, session_id=session_id, index=index)
    if not ans.chosen:
        ans.chosen = request.POST["choice"]
        ans.is_correct = ans.chosen == ans.correct_choice
        ms = request.POST.get("response_ms")
        ans.response_ms = int(ms) if ms and ms.isdigit() else None
        ans.answered_at = timezone.now()
        ans.save()
        session = ans.session
        if not session.answers.filter(chosen="").exists():
            session.finished = timezone.now()
            session.save(update_fields=["finished"])
    return redirect("quiz:question", session_id, index)


def results(request, session_id):
    session = get_object_or_404(QuizSession, pk=session_id)
    answers = list(session.answers.select_related("asset", "taxon"))
    chosen = {t.species_code: t for t in Taxon.objects.filter(species_code__in=[a.chosen for a in answers])}
    for a in answers:
        a.chosen_taxon = chosen.get(a.chosen)
    misses = [a for a in answers if a.is_correct is False]
    correct, answered, total = session.score
    return render(
        request,
        "quiz/results.html",
        {
            "session": session,
            "answers": answers,
            "misses": misses,
            "correct": correct,
            "answered": answered,
            "total": total,
            "OTHER": OTHER,
            "miss_codes": ",".join(sorted({a.taxon.species_code for a in misses})),
        },
    )


@require_POST
def requiz(request, session_id):
    session = get_object_or_404(QuizSession, pk=session_id)
    st = dict(session.settings)
    st["species"] = [c for c in request.POST.get("species", "").split(",") if c]
    st["seed"] = None
    try:
        new = build_quiz(QuizSettings(**st))
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("quiz:results", session.pk)
    return redirect("quiz:question", new.pk, 0)
