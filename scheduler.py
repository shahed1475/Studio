"""Publish slots: the next free time in the audience's time zone, as a UTC instant."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SLOTS_DEFAULT = [  # America/New_York: evening, weekend morning, weekday afternoon
    {"day": "fri", "time": "18:00"},
    {"day": "sun", "time": "10:00"},
    {"day": "thu", "time": "15:00"},
]


SHORT_SLOTS_DEFAULT = [  # America/New_York: one a day, midday on weekdays, Friday late afternoon, weekend early afternoon
    {"day": "mon", "time": "12:30"},
    {"day": "tue", "time": "12:30"},
    {"day": "wed", "time": "12:30"},
    {"day": "thu", "time": "12:30"},
    {"day": "fri", "time": "16:00"},
    {"day": "sat", "time": "13:00"},
    {"day": "sun", "time": "13:00"},
]


def next_slot(now: datetime, slots: list[dict], taken: list[datetime], min_lead_hours: float = 24,
              tz: str = "America/New_York") -> datetime:
    """Earliest slot at least min_lead_hours away and not within 6 h of an already-taken time."""
    zone = ZoneInfo(tz)
    earliest = now + timedelta(hours=min_lead_hours)
    local_today = now.astimezone(zone).date()
    candidates = []
    for offset in range(0, 22):
        day = local_today + timedelta(days=offset)
        for s in slots:
            if DAYS[day.weekday()] != s["day"]:
                continue
            hh, mm = map(int, s["time"].split(":"))
            candidates.append(datetime.combine(day, time(hh, mm), tzinfo=zone).astimezone(timezone.utc))
    for c in sorted(candidates):
        if c >= earliest and all(abs((c - t).total_seconds()) >= 6 * 3600 for t in taken):
            return c
    raise ValueError("no free slot in the next 3 weeks")


def to_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_local(dt: datetime, tz: str) -> str:
    return dt.astimezone(ZoneInfo(tz)).strftime("%a %-d %b, %H:%M")
