import time

from django.core.management.base import BaseCommand, CommandError

from plan.tsdb import ensure_schema

ATTEMPTS = 30


class Command(BaseCommand):
    help = "Create the ClickHouse database and work_volume_record table (idempotent)."

    def handle(self, *args, **options):
        last = None
        for attempt in range(1, ATTEMPTS + 1):
            try:
                ensure_schema()
                self.stdout.write(self.style.SUCCESS("ClickHouse schema is ready"))
                return
            except Exception as e:  # noqa: BLE001 - retry on any connectivity problem
                last = e
                self.stderr.write(f"ClickHouse not ready ({attempt}/{ATTEMPTS}): {e}")
                time.sleep(1)
        raise CommandError(f"ClickHouse schema initialization failed: {last}")
