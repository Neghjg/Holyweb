import pytest
from rest_framework.exceptions import ValidationError

from plan.constants import MAX_DATE_TS
from plan.fields import StrictIntegerField, UnixMidnightDateField


@pytest.mark.parametrize("value", [True, "5", 5.0, None])
def test_strict_integer_rejects(value):
    with pytest.raises(ValidationError):
        StrictIntegerField().run_validation(value)


def test_strict_integer_accepts():
    assert StrictIntegerField().run_validation(5) == 5


@pytest.mark.parametrize("value", [0, MAX_DATE_TS])
def test_date_field_accepts_bounds(value):
    f = UnixMidnightDateField()
    assert f.to_representation(f.run_validation(value)) == value


@pytest.mark.parametrize(
    "value", [-86400, MAX_DATE_TS + 86400, 1735689601, 1735689600000, "0", True]
)
def test_date_field_rejects(value):
    with pytest.raises(ValidationError):
        UnixMidnightDateField().run_validation(value)


def test_date_field_roundtrip():
    f = UnixMidnightDateField()
    assert f.to_representation(f.to_internal_value(1735689600)) == 1735689600
