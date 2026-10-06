from django.urls import path

from .views import WorkVolumeListView

urlpatterns = [
    path("work-volume-list/", WorkVolumeListView.as_view(), name="work-volume-list"),
]
