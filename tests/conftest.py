import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from plan import services
from plan.constants import GROUP_FACTORY_MANAGER, GROUP_FACTORY_REPRESENTATIVE
from plan.errors import TsDBUnavailable
from plan.models import Factory, FactoryUser

START_TS = 1735689600  # 2025-01-01
FINISH_TS = 1738281600  # 2025-01-31


class FakeRepo:
    def __init__(self):
        self.records = []

    def add(self, record):
        self.records.append(record)


class FailingRepo:
    def add(self, record):
        raise TsDBUnavailable()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def factory_a(db):
    return Factory.objects.create(name="A")


@pytest.fixture
def factory_b(db):
    return Factory.objects.create(name="B")


def _make_user(username, *group_names):
    user = get_user_model().objects.create_user(username=username, password="pw12345678")
    for name in group_names:
        user.groups.add(Group.objects.get(name=name))
    return user


@pytest.fixture
def rep_user(factory_a):
    user = _make_user("rep", GROUP_FACTORY_REPRESENTATIVE)
    FactoryUser.objects.create(user=user, factory=factory_a)
    return user


@pytest.fixture
def manager_user(db):
    return _make_user("manager", GROUP_FACTORY_MANAGER)


@pytest.fixture
def both_roles_user(db):
    return _make_user("both", GROUP_FACTORY_REPRESENTATIVE, GROUP_FACTORY_MANAGER)


@pytest.fixture
def nobody_user(db):
    return _make_user("nobody")


@pytest.fixture
def fake_tsdb(monkeypatch):
    repo = FakeRepo()
    monkeypatch.setattr(services, "get_work_volume_record_repository", lambda: repo)
    return repo.records


@pytest.fixture
def failing_tsdb(monkeypatch):
    monkeypatch.setattr(services, "get_work_volume_record_repository", lambda: FailingRepo())


@pytest.fixture
def payload(factory_a):
    def make(**overrides):
        body = {
            "factory": factory_a.pk,
            "start": START_TS,
            "finish": FINISH_TS,
            "weight": 1500,
            "author": 0,
        }
        body.update(overrides)
        return body

    return make
