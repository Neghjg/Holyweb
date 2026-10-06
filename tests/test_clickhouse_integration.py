import datetime
import uuid

import pytest

from plan import tsdb

pytestmark = pytest.mark.clickhouse


def test_roundtrip():
    tsdb.ensure_schema()
    tsdb.ensure_schema()  # idempotent
    fid = uuid.uuid4()
    tsdb.get_work_volume_record_repository().add(
        tsdb.WorkVolumeRecordDTO(
            factory=fid,
            start=datetime.date(2025, 1, 1),
            finish=datetime.date(2025, 1, 31),
            weight=10,
            author=1,
            created=datetime.datetime.now(datetime.UTC),
        )
    )
    client = tsdb.get_clickhouse_client()
    count = client.query(
        f"SELECT count() FROM {tsdb._database_name()}.{tsdb.TABLE_NAME} WHERE factory = %(f)s",
        parameters={"f": str(fid)},
    ).first_row[0]
    assert count == 1
