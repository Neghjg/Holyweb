import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Factory(models.Model):
    external_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField("наименование", max_length=255)

    class Meta:
        verbose_name = "ЗМК"
        verbose_name_plural = "ЗМК"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class FactoryUser(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="factory_links"
    )
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, related_name="user_links")

    class Meta:
        verbose_name = "Пользователь завода"
        verbose_name_plural = "Пользователи завода"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "factory"], name="uniq_factory_user"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.factory}"


class WorkVolume(models.Model):
    factory = models.ForeignKey(Factory, on_delete=models.PROTECT, related_name="work_volumes")
    start = models.DateField("начальная дата")
    finish = models.DateField("конечная дата")
    weight = models.PositiveIntegerField("вес, кг")
    created = models.DateTimeField("дата последнего сохранения")

    class Meta:
        verbose_name = "Объем работы"
        verbose_name_plural = "Объемы работы"
        ordering = ["-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["factory", "start", "finish"], name="uniq_work_volume_factory_period"
            ),
            models.CheckConstraint(
                condition=Q(start__lte=F("finish")), name="work_volume_start_lte_finish"
            ),
            models.CheckConstraint(condition=Q(weight__gte=0), name="work_volume_weight_gte_0"),
        ]

    def __str__(self) -> str:
        return f"{self.factory} {self.start}..{self.finish}: {self.weight}"
