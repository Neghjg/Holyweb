from rest_framework import serializers

from .constants import MAX_WEIGHT, REQUIRED_FIELDS
from .fields import StrictIntegerField, UnixMidnightDateField
from .models import WorkVolume


def check_required_fields(data: dict) -> list[str]:
    """Names of required fields that are absent, null or an empty string."""
    return [f for f in REQUIRED_FIELDS if data.get(f) is None or data.get(f) == ""]


class WorkVolumeRequestSerializer(serializers.Serializer):
    factory = StrictIntegerField(min_value=1)
    start = UnixMidnightDateField()
    finish = UnixMidnightDateField()
    weight = StrictIntegerField(min_value=0, max_value=MAX_WEIGHT)
    author = StrictIntegerField(min_value=1)

    def validate(self, attrs):
        if attrs["start"] > attrs["finish"]:
            raise serializers.ValidationError({"finish": ["finish must be >= start"]})
        return attrs


class WorkVolumeResponseSerializer(serializers.ModelSerializer):
    start = UnixMidnightDateField()
    finish = UnixMidnightDateField()

    class Meta:
        model = WorkVolume
        fields = ["id", "factory", "start", "finish", "weight", "created"]
