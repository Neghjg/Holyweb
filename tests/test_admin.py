import pytest
from django.contrib import admin
from django.test import RequestFactory

from plan.models import Factory, FactoryUser, WorkVolume


@pytest.fixture
def request_obj(django_user_model):
    req = RequestFactory().get("/admin/")
    req.user = django_user_model(is_active=True, is_staff=True, is_superuser=True)
    return req


@pytest.mark.django_db
def test_work_volume_admin_is_read_only(request_obj):
    ma = admin.site._registry[WorkVolume]
    assert not ma.has_add_permission(request_obj)
    assert not ma.has_change_permission(request_obj)
    assert not ma.has_delete_permission(request_obj)


@pytest.mark.django_db
@pytest.mark.parametrize("model", [Factory, FactoryUser])
def test_other_models_stay_editable(request_obj, model):
    ma = admin.site._registry[model]
    assert ma.has_add_permission(request_obj)
    assert ma.has_change_permission(request_obj)
