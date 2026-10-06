from django.urls import re_path

from .views import WorkVolumeListView

urlpatterns = [
    re_path(r"^work-volume-list/?$", WorkVolumeListView.as_view(), name="work-volume-list"),
]
