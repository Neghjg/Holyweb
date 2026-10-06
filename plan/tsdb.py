"""ClickHouse (tsDB) access layer: the only module that knows about the driver."""

import logging
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

import clickhouse_connect
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .errors import TsDBUnavailable

logger = logging.getLogger(__name__)

TABLE_NAME = "work_volume_record"
_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")

CREATE_DATABASE_SQL = "CREATE DATABASE IF NOT EXISTS {db}"
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {db}.{table}
(
    id       UInt64 DEFAULT generateSnowflakeID(),
    factory  UUID,
    start    Date,
    finish   Date,
    weight   UInt32,
    author   UInt64,
    created  DateTime64(6, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created)
ORDER BY (factory, start, finish, created)
"""

INSERT_COLUMNS = ["factory", "start", "finish", "weight", "author", "created"]

_client = None
_client_lock = threading.Lock()


@dataclass(frozen=True)
class WorkVolumeRecordDTO:
    factory: UUID
    start: date
    finish: date
    weight: int
    author: int
    created: datetime


def _database_name() -> str:
    db = settings.CLICKHOUSE["database"]
    if not _IDENT_RE.match(db or ""):
        raise ImproperlyConfigured("CLICKHOUSE_DATABASE must match [A-Za-z0-9_]+")
    return db


def _connect(database: str | None):
    cfg = settings.CLICKHOUSE
    kwargs = {
        "host": cfg["host"],
        "port": cfg["port"],
        "username": cfg["username"],
        "password": cfg["password"],
        "connect_timeout": cfg["connect_timeout"],
        "send_receive_timeout": cfg["send_receive_timeout"],
        # A cached client may be shared by threads; a fixed session id would make
        # concurrent queries fail with "concurrent queries within the same session".
        "autogenerate_session_id": False,
    }
    if database:
        kwargs["database"] = database
    return clickhouse_connect.get_client(**kwargs)


def get_clickhouse_client():
    """Lazy, cached, thread-safe client bound to the configured database."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = _connect(_database_name())
    return _client


def ensure_schema() -> None:
    """Idempotently create the database and the table."""
    db = _database_name()
    client = _connect(None)
    try:
        client.command(CREATE_DATABASE_SQL.format(db=db))
        client.command(CREATE_TABLE_SQL.format(db=db, table=TABLE_NAME))
    finally:
        client.close()


class ClickHouseWorkVolumeRecordRepository:
    def add(self, record: WorkVolumeRecordDTO) -> None:
        table = f"{_database_name()}.{TABLE_NAME}"
        try:
            client = get_clickhouse_client()
            client.insert(
                table,
                [
                    [
                        record.factory,
                        record.start,
                        record.finish,
                        record.weight,
                        record.author,
                        record.created,
                    ]
                ],
                column_names=INSERT_COLUMNS,
                settings={"async_insert": 0},
            )
        except Exception as e:  # any driver/network/timeout failure -> 503/904, PG rolls back
            logger.warning("ClickHouse insert failed: %r", e)
            raise TsDBUnavailable() from e


def get_work_volume_record_repository() -> ClickHouseWorkVolumeRecordRepository:
    return ClickHouseWorkVolumeRecordRepository()
