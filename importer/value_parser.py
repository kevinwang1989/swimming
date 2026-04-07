"""Parse raw result values from the PDF into numeric values and status flags."""

import re
from typing import Optional, Tuple


def parse_time(raw: str) -> Optional[float]:
    """Convert time string like '01:04.56' or '00:55.38' to total seconds.
    Returns None if not a valid time format.
    """
    m = re.match(r'^(\d{2}):(\d{2})\.(\d{2})$', raw.strip())
    if m:
        minutes = int(m.group(1))
        seconds = int(m.group(2))
        centiseconds = int(m.group(3))
        return minutes * 60 + seconds + centiseconds / 100.0
    return None


def parse_result(raw_value: Optional[str], result_type: str = 'time') -> Tuple[Optional[float], str]:
    """Parse a raw result value into (numeric_value, status).

    Args:
        raw_value: The raw string from the PDF cell
        result_type: 'time', 'count', or 'distance'

    Returns:
        (numeric_value: float|None, status: str)
        status is one of: 'normal', 'foul', 'withdrew', 'missing'
    """
    if raw_value is None or raw_value.strip() == '':
        return None, 'missing'

    val = raw_value.strip()

    if val == '犯规':
        return None, 'foul'
    if val in ('弃权', ''):
        return None, 'withdrew'

    if result_type == 'time':
        numeric = parse_time(val)
        if numeric is not None:
            return numeric, 'normal'
        return None, 'missing'

    if result_type in ('count', 'distance'):
        try:
            numeric = float(val)
            return numeric, 'normal'
        except ValueError:
            return None, 'missing'

    return None, 'missing'


def format_time(seconds: float) -> str:
    """Convert total seconds back to display format MM:SS.ss"""
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    return f"{minutes:02d}:{secs:05.2f}"
