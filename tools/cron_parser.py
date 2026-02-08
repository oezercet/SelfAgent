"""Cron expression and interval parsing utilities.

Provides functions for parsing and matching cron expressions (5-field standard
format) and simple interval strings ('every 5m', 'every 2h', etc.).

Extracted from scheduler.py to keep each module under 300 lines.
"""

import re
from datetime import datetime


def parse_cron(expr: str) -> list | None:
    """Parse a 5-field cron expression.

    Args:
        expr: A standard cron expression like '*/5 * * * *'.

    Returns:
        A list of 5 field strings, or None if the expression is invalid.
    """
    expr = expr.strip()
    fields = expr.split()
    if len(fields) != 5:
        return None
    # Basic validation: each field should contain digits, *, /, -, or ,
    for f in fields:
        if not re.match(r'^[\d*/,\-]+$', f):
            return None
    return fields


def cron_matches(cron_expr: str, dt: datetime) -> bool:
    """Check if a datetime matches a cron expression.

    Args:
        cron_expr: A 5-field cron expression string.
        dt: The datetime to check against.

    Returns:
        True if the datetime matches the cron expression, False otherwise.
    """
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return False

    values = [dt.minute, dt.hour, dt.day, dt.month, dt.weekday()]
    # Cron weekday: 0=Sunday, Python weekday: 0=Monday
    # Convert Python weekday to cron weekday
    cron_weekday = (dt.weekday() + 1) % 7  # Mon=1..Sun=0
    values[4] = cron_weekday

    maxvals = [59, 23, 31, 12, 6]

    for field, val, maxval in zip(fields, values, maxvals):
        if not cron_field_matches(field, val, maxval):
            return False
    return True


def cron_field_matches(field: str, value: int, max_val: int) -> bool:
    """Check if a single cron field matches a value.

    Supports wildcards (*), steps (*/5, 1/3), ranges (1-5), and
    comma-separated lists (1,3,5).

    Args:
        field: A single cron field string.
        value: The current value to check (e.g. current minute).
        max_val: The maximum allowed value for this field.

    Returns:
        True if the value matches the field specification.
    """
    for part in field.split(","):
        if "/" in part:
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                if value % step == 0:
                    return True
            else:
                start = int(base)
                if value >= start and (value - start) % step == 0:
                    return True
        elif "-" in part:
            start, end = part.split("-", 1)
            if int(start) <= value <= int(end):
                return True
        elif part == "*":
            return True
        else:
            if int(part) == value:
                return True
    return False


def parse_interval(expr: str) -> int | None:
    """Parse an interval expression into seconds.

    Supports formats like 'every 5m', 'every 2h', 'every 1d', or
    bare forms like '5m', '2h', '1d'.

    Supported units:
        s - seconds
        m - minutes
        h - hours
        d - days

    Args:
        expr: The interval expression string.

    Returns:
        The interval in seconds, or None if the expression is invalid.
    """
    expr = expr.strip().lower()
    if expr.startswith("every "):
        expr = expr[6:].strip()

    if not expr:
        return None

    unit = expr[-1]
    try:
        value = int(expr[:-1])
    except ValueError:
        return None

    if unit == "s":
        return value
    elif unit == "m":
        return value * 60
    elif unit == "h":
        return value * 3600
    elif unit == "d":
        return value * 86400
    return None
