"""Date utility functions."""

from datetime import date, datetime, timedelta
from typing import Tuple, List


def days_ago(n: int) -> date:
    """Get the date n days ago."""
    return date.today() - timedelta(days=n)


def get_date_range(days: int) -> Tuple[date, date]:
    """Get a date range from n days ago to yesterday."""
    end_date = date.today() - timedelta(days=1)  # Yesterday
    start_date = end_date - timedelta(days=days - 1)
    return start_date, end_date


def date_to_string(d: date, format: str = "%Y-%m-%d") -> str:
    """Convert date to string."""
    return d.strftime(format)


def string_to_date(s: str, format: str = "%Y-%m-%d") -> date:
    """Convert string to date."""
    return datetime.strptime(s, format).date()


def get_time_windows() -> List[int]:
    """Get standard time windows for analysis."""
    return [1, 3, 7, 14, 30, 60, 90]


def is_same_week(d1: date, d2: date) -> bool:
    """Check if two dates are in the same week."""
    return d1.isocalendar()[1] == d2.isocalendar()[1] and d1.year == d2.year


def get_day_of_week_name(d: date) -> str:
    """Get day of week name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[d.weekday()]
