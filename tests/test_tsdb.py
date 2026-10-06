import datetime
import uuid
from unittest import mock

import pytest
from clickhouse_connect.driver.exceptions import ClickHouseError
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from plan import tsdb
from plan.errors import TsDBUnavailable


def test_ensure_schema_runs_ddl():
    client = mock.Mock()
    with mock.patch.object(tsdb, "_connect", return_value=client):
        tsdb.ensure_schema()
    sqls = [c.args[0] for c in client.command.call_args_list]
    assert any("CREATE DATABASE IF NOT EXISTS" in s for s in sqls)
    assert any("CREATE TABLE IF NOT EXISTS" in s and "MergeTree" in s for s in sqls)


def _dto():
    return tsdb.WorkVolumeRecordDTO(
        factory=uuid.uuid4(),
        start=datetime.date(2025, 1, 1),
        finish=datetime.date(2025, 1, 31),
        weight=5,
        author=7,
        created=datetime.datetime.now(datetime.UTC),
    )


def test_add_inserts_in_column_order():
    client = mock.Mock()
    dto = _dto()
    with mock.patch.object(tsdb, "get_clickhouse_client", return_value=client):
        tsdb.ClickHouseWorkVolumeRecordRepository().add(dto)
    args, kwargs = client.insert.call_args
    assert args[1] == [[dto.factory, dto.start, dto.finish, dto.weight, dto.author, dto.created]]
    assert kwargs["column_names"] == ["factory", "start", "finish", "weight", "author", "created"]
    assert kwargs["settings"] == {"async_insert": 0}


@pytest.mark.parametrize("exc", [ClickHouseError("boom"), OSError("down")])
def test_driver_errors_wrapped(exc):
    client = mock.Mock()
    client.insert.side_effect = exc
    with mock.patch.object(tsdb, "get_clickhouse_client", return_value=client):
        with pytest.raises(TsDBUnavailable):
            tsdb.ClickHouseWorkVolumeRecordRepository().add(_dto())


def test_invalid_database_name():
    with override_settings(CLICKHOUSE={**tsdb.settings.CLICKHOUSE, "database": "a; DROP"}):
        with pytest.raises(ImproperlyConfigured):
            tsdb.ensure_schema()
