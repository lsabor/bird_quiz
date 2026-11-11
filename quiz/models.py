from django.db import models

from birds.models import MediaAsset, Taxon, TripSet

OTHER = "other"


class QuizSession(models.Model):
    trip_set = models.ForeignKey(TripSet, on_delete=models.CASCADE, related_name="quiz_sessions")
    settings = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Quiz {self.pk} ({self.trip_set.slug}, {self.created:%Y-%m-%d %H:%M})"

    @property
    def score(self):
        answered = self.answers.exclude(chosen="")
        return answered.filter(is_correct=True).count(), answered.count(), self.answers.count()


class QuizAnswer(models.Model):
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name="answers")
    index = models.PositiveSmallIntegerField()
    asset = models.ForeignKey(MediaAsset, on_delete=models.CASCADE, related_name="quiz_answers")
    taxon = models.ForeignKey(Taxon, on_delete=models.CASCADE, related_name="quiz_answers")
    options = models.JSONField(help_text="species codes shown, in order")
    correct_choice = models.CharField(max_length=16, help_text="species code, or 'other'")
    chosen = models.CharField(max_length=16, blank=True)
    is_correct = models.BooleanField(null=True)
    response_ms = models.PositiveIntegerField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["session", "index"]
        unique_together = [("session", "index")]
