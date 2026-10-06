import pytest
from django.contrib.auth.models import Group


@pytest.mark.django_db
def test_groups_exist():
    names = set(Group.objects.values_list("name", flat=True))
    assert {"Представитель ЗМК", "Менеджер по взаимодействию с ЗМК"} <= names
