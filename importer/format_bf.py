"""Parser for B-F组 format.

Table structure: 34 columns
  [0] 排名  [1] 所属区  [2] 姓名  [3] 总分  [4] 评级  [5] 备注
  Then 14 event pairs (成绩, 得分) at columns [6,7], [8,9], ..., [32,33]

Each person has results in MULTIPLE events.
"""


def parse_header(header_row):
    """Extract event names from the header row.
    Event names are at indices 6, 8, 10, ..., 32.
    """
    events = []
    for i in range(6, len(header_row), 2):
        name = header_row[i]
        if name and name.strip():
            events.append((i, name.strip()))
        else:
            events.append((i, None))
    return events


def fill_event_names(events):
    """Forward-fill None event names (from merged header cells).
    This shouldn't happen in practice since headers are explicit,
    but handle defensively.
    """
    filled = []
    last_name = None
    for col_idx, name in events:
        if name is not None:
            last_name = name
        filled.append((col_idx, name if name else last_name))
    return filled


def parse_rows(rows, header_row):
    """Parse data rows for B-F组 format.

    Returns list of dicts with same structure as format_a.parse_rows,
    plus 'rating' field.
    """
    events = fill_event_names(parse_header(header_row))
    parsed = []

    for row in rows:
        if not row or len(row) < 6:
            continue

        rank_str = (row[0] or '').strip()
        if not rank_str or not rank_str.isdigit():
            continue

        record = {
            'rank': int(rank_str),
            'district': (row[1] or '').strip(),
            'name': (row[2] or '').strip(),
            'total_score': float(row[3]) if row[3] and row[3].strip() else None,
            'rating': (row[4] or '').strip() or None,
            'remark': (row[5] or '').strip() or None,
            'results': [],
        }

        if not record['name']:
            continue

        for col_idx, event_name in events:
            if event_name is None:
                continue
            if col_idx + 1 >= len(row):
                continue

            raw = (row[col_idx] or '').strip()
            score_str = (row[col_idx + 1] or '').strip()

            # Skip empty cells (no result for this event)
            if not raw and not score_str:
                continue

            # Handle score being '弃权' or similar
            score = None
            if score_str and score_str not in ('弃权', '犯规'):
                try:
                    score = float(score_str)
                except ValueError:
                    pass

            # If raw is empty but score exists, or raw has a value
            if raw or score_str:
                record['results'].append({
                    'event': event_name,
                    'raw_value': raw if raw else score_str,
                    'score': score,
                })

        parsed.append(record)

    return parsed
