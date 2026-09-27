from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


WARSAW = ZoneInfo("Europe/Warsaw")


def inspection_date_time(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=WARSAW).astimezone(UTC)
