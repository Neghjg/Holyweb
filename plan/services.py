import logging
from datetime import date

from django.db import transaction
from django.utils import timezone

from . import tsdb
from .constants import GROUP_FACTORY_MANAGER, GROUP_FACTORY_REPRESENTATIVE
from .errors import AuthorMismatch, FactoryNotFound, NoPermittedGroup, TsDBUnavailable
from .models import Factory, FactoryUser, WorkVolume
from .tsdb import WorkVolumeRecordDTO

logger = logging.getLogger(__name__)


def get_work_volume_record_repository():
    # Indirection: tests monkeypatch this name.
    return tsdb.get_work_volume_record_repository()


def save_work_volume(
    *,
    user,
    factory_id: int,
    start: date,
    finish: date,
    weight: int,
    author_id: int,
    repo=None,
) -> WorkVolume:
    factory = Factory.objects.filter(pk=factory_id).first()
    if factory is None:
        raise FactoryNotFound()

    if author_id != user.pk:
        raise AuthorMismatch()

    groups = set(user.groups.values_list("name", flat=True))
    if GROUP_FACTORY_MANAGER in groups:
        pass  # manager has priority over representative
    elif GROUP_FACTORY_REPRESENTATIVE in groups:
        if not FactoryUser.objects.filter(user=user, factory=factory).exists():
            # Interpretation of the diagram's "ЗМК не существует": the factory does
            # not exist *for this user*, so foreign factories are not disclosed.
            raise FactoryNotFound()
    else:
        raise NoPermittedGroup()

    repo = repo or get_work_volume_record_repository()
    now = timezone.now()
    try:
        with transaction.atomic():
            obj = WorkVolume(
                factory=factory, start=start, finish=finish, weight=weight, created=now
            )
            WorkVolume.objects.bulk_create(
                [obj],
                update_conflicts=True,
                unique_fields=["factory", "start", "finish"],
                update_fields=["weight", "created"],
            )
            if obj.pk is None:
                obj = WorkVolume.objects.get(factory=factory, start=start, finish=finish)
            repo.add(
                WorkVolumeRecordDTO(
                    factory=factory.external_id,
                    start=start,
                    finish=finish,
                    weight=weight,
                    author=user.pk,
                    created=now,
                )
            )
    except TsDBUnavailable:
        logger.warning(
            "tsDB unavailable, work volume change rolled back (factory_id=%s)", factory_id
        )
        raise

    logger.info(
        "work volume saved factory_id=%s period=%s..%s user_id=%s",
        factory.pk,
        start,
        finish,
        user.pk,
    )
    return obj
