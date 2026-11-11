from django.urls import path

from . import views

app_name = "quiz"
urlpatterns = [
    path("", views.setup, name="setup"),
    path("q/<int:session_id>/<int:index>/", views.question, name="question"),
    path("q/<int:session_id>/<int:index>/answer/", views.answer, name="answer"),
    path("q/<int:session_id>/results/", views.results, name="results"),
    path("q/<int:session_id>/requiz/", views.requiz, name="requiz"),
]
