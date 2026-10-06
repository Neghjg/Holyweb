import datetime

import pytest

from plan.errors import AuthorMismatch, FactoryNotFound, NoPermittedGroup, TsDBUnavailable
from plan.models import WorkVolume
from plan.services import save_work_volume
from plan.tsdb import WorkVolumeRecordDTO

S = datetime.date(2025, 1, 1)
F = datetime.date(2025, 1, 31)


class Repo:
    def __init__(self):
        self.records = []

    def add(self, record):
        self.records.append(record)


def call(user, factory, repo, weight=100, author=None, factory_id=None):
    return save_work_volume(
        user=user,
        factory_id=factory_id or factory.pk,
        start=S,
        finish=F,
        weight=weight,
        author_id=author or user.pk,
        repo=repo,
    )


def test_manager_creates_and_dto(manager_user, factory_a):
    repo = Repo()
    wv = call(manager_user, factory_a, repo)
    assert len(repo.records) == 1
    dto = repo.records[0]
    assert isinstance(dto, WorkVolumeRecordDTO)
    assert dto.factory == factory_a.external_id
    assert dto.author == manager_user.pk
    assert dto.created == wv.created
    assert (dto.start, dto.finish, dto.weight) == (S, F, 100)


def test_upsert(manager_user, factory_a):
    repo = Repo()
    first = call(manager_user, factory_a, repo, weight=1)
    second = call(manager_user, factory_a, repo, weight=2)
    assert WorkVolume.objects.count() == 1
    assert WorkVolume.objects.get().weight == 2
    assert second.created > first.created
    assert len(repo.records) == 2


def test_rep_own_and_foreign(rep_user, factory_a, factory_b):
    repo = Repo()
    call(rep_user, factory_a, repo)
    with pytest.raises(FactoryNotFound):
        call(rep_user, factory_b, repo)
    assert len(repo.records) == 1


def test_nobody(nobody_user, factory_a):
    with pytest.raises(NoPermittedGroup):
        call(nobody_user, factory_a, Repo())


def test_unknown_factory(manager_user):
    with pytest.raises(FactoryNotFound):
        call(manager_user, None, Repo(), factory_id=99999)


def test_author_mismatch(manager_user, factory_a):
    with pytest.raises(AuthorMismatch):
        call(manager_user, factory_a, Repo(), author=manager_user.pk + 1)


def test_both_roles_priority(both_roles_user, factory_b):
    call(both_roles_user, factory_b, Repo())


def test_rollback_on_tsdb_failure(manager_user, factory_a):
    class Bad:
        def add(self, record):
            raise TsDBUnavailable()

    with pytest.raises(TsDBUnavailable):
        call(manager_user, factory_a, Bad())
    assert WorkVolume.objects.count() == 0
