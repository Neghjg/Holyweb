import pytest
from django.contrib.auth.models import Group


@pytest.mark.django_db
def test_groups_exist():
    names = set(Group.objects.values_list("name", flat=True))
    assert {"Представитель ЗМК", "Менеджер по взаимодействию с ЗМК"} <= names


@pytest.mark.django_db(transaction=True)
def test_groups_migration_is_reversible():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    names = ["Представитель ЗМК", "Менеджер по взаимодействию с ЗМК"]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate([("plan", "0001_initial")])
        assert not Group.objects.filter(name__in=names).exists()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
    assert Group.objects.filter(name__in=names).count() == 2
