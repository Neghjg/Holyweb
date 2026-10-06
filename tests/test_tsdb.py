import datetime
import re
import uuid
from pathlib import Path
from unittest import mock

import pytest
import urllib3.exceptions
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


def test_connect_passes_configured_timeouts():
    cfg = {**tsdb.settings.CLICKHOUSE, "connect_timeout": 1.5, "send_receive_timeout": 2.5}
    with override_settings(CLICKHOUSE=cfg):
        with mock.patch.object(tsdb.clickhouse_connect, "get_client") as get_client:
            tsdb._connect("plan")
    kwargs = get_client.call_args.kwargs
    assert kwargs["connect_timeout"] == 1.5
    assert kwargs["send_receive_timeout"] == 2.5
    assert kwargs["autogenerate_session_id"] is False


def test_default_timeouts_stay_below_gunicorn_timeout():
    cmd = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text()
    gunicorn_timeout = int(re.search(r"--timeout\D+(\d+)", cmd).group(1))
    cfg = tsdb.settings.CLICKHOUSE
    assert cfg["connect_timeout"] + cfg["send_receive_timeout"] < gunicorn_timeout


def test_programming_errors_are_not_masked():
    client = mock.Mock()
    client.insert.side_effect = TypeError("bug")
    with mock.patch.object(tsdb, "get_clickhouse_client", return_value=client):
        with pytest.raises(TypeError):
            tsdb.ClickHouseWorkVolumeRecordRepository().add(_dto())


def test_urllib3_error_wrapped():
    client = mock.Mock()
    client.insert.side_effect = urllib3.exceptions.HTTPError("conn")
    with mock.patch.object(tsdb, "get_clickhouse_client", return_value=client):
        with pytest.raises(TsDBUnavailable):
            tsdb.ClickHouseWorkVolumeRecordRepository().add(_dto())


def test_timeout_wrapped_as_unavailable():
    from clickhouse_connect.driver.exceptions import OperationalError

    client = mock.Mock()
    client.insert.side_effect = OperationalError("Read timed out")
    with mock.patch.object(tsdb, "get_clickhouse_client", return_value=client):
        with pytest.raises(TsDBUnavailable):
            tsdb.ClickHouseWorkVolumeRecordRepository().add(_dto())
