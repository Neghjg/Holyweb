from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("plan.urls")),
]

handler404 = "plan.errors.not_found_view"
