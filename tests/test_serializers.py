from plan.constants import REQUIRED_FIELDS
from plan.serializers import WorkVolumeRequestSerializer, check_required_fields

BASE = {"factory": 1, "start": 1735689600, "finish": 1738281600, "weight": 10, "author": 1}


def errors(**overrides):
    s = WorkVolumeRequestSerializer(data={**BASE, **overrides})
    s.is_valid()
    return s.errors


def test_required_all_missing_in_order():
    assert check_required_fields({}) == list(REQUIRED_FIELDS)


def test_required_null_and_empty_are_missing_zero_is_not():
    data = {**BASE, "start": None, "finish": "", "weight": 0}
    assert check_required_fields(data) == ["start", "finish"]


def test_start_after_finish():
    assert "finish" in errors(start=1738281600, finish=1735689600)


def test_start_equals_finish_ok():
    assert errors(finish=BASE["start"]) == {}


def test_weight_bounds():
    assert errors(weight=0) == {}
    assert "weight" in errors(weight=-1)


def test_extra_field_ignored():
    s = WorkVolumeRequestSerializer(data={**BASE, "extra": 1})
    assert s.is_valid()
    assert "extra" not in s.validated_data
