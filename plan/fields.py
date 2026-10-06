from datetime import UTC, date, datetime

from rest_framework import serializers

from .constants import MAX_DATE_TS, SECONDS_PER_DAY


class StrictIntegerField(serializers.IntegerField):
    """Accepts only real JSON integers: no bool, str or float."""

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class UnixMidnightDateField(serializers.Field):
    """Unix timestamp (seconds) on a UTC midnight <-> datetime.date."""

    default_error_messages = {
        "invalid": "Must be an integer unix timestamp in seconds.",
        "not_midnight": "Must be a UTC midnight unix timestamp (seconds).",
        "out_of_range": f"Must be in range 0..{MAX_DATE_TS} (1970-01-01..2149-06-06).",
    }

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        if data < 0 or data > MAX_DATE_TS:
            self.fail("out_of_range")
        if data % SECONDS_PER_DAY != 0:
            self.fail("not_midnight")
        return datetime.fromtimestamp(data, tz=UTC).date()

    def to_representation(self, value: date) -> int:
        return int(datetime(value.year, value.month, value.day, tzinfo=UTC).timestamp())
