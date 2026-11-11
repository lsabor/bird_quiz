from django.contrib import admin

from .models import QuizAnswer, QuizSession


class QuizAnswerInline(admin.TabularInline):
    model = QuizAnswer
    extra = 0
    raw_id_fields = ["asset", "taxon"]


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "trip_set", "created", "finished"]
    inlines = [QuizAnswerInline]
