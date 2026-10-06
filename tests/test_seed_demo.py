import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from plan.models import Factory

pytestmark = pytest.mark.django_db


def test_seed_does_not_touch_existing_users():
    User = get_user_model()
    User.objects.create_user(username="manager", password="changed-secret-1")
    call_command("seed_demo")
    manager = User.objects.get(username="manager")
    assert manager.check_password("changed-secret-1")
    assert manager.groups.count() == 0
    # idempotent
    call_command("seed_demo")
    assert User.objects.filter(username="rep").count() == 1
    assert get_user_model().objects.get(username="rep").factory_links.count() == 1


def test_seed_tolerates_duplicate_factory_names():
    Factory.objects.create(name="ЗМК Север")
    Factory.objects.create(name="ЗМК Север")
    call_command("seed_demo")
    assert Factory.objects.filter(name="ЗМК Север").count() == 2
