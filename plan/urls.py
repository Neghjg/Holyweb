from django.urls import path

from .views import WorkVolumeListView

urlpatterns = [
    path("work-volume-list/", WorkVolumeListView.as_view(), name="work-volume-list"),
    # The path without a trailing slash is accepted too (APPEND_SLASH cannot redirect a POST).
    path("work-volume-list", WorkVolumeListView.as_view()),
]
