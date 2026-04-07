"""Parser for A组 format (男子A组, 女子A组).

Table structure: 17 columns
  [0] 排名  [1] 所属区  [2] 姓名  [3] 总分  [4] 备注
  Then 6 event pairs (成绩, 得分) at columns [5,6], [7,8], ..., [15,16]

Each person only has results in ONE event.
"""


def parse_header(header_row):
    """Extract event names from the header row.
    Event names are at indices 5, 7, 9, 11, 13, 15.
    """
    events = []
    for i in range(5, len(header_row), 2):
        name = header_row[i]
        if name and name.strip():
            # Clean A组 suffix like "100米自由泳（A组）"
            clean = name.replace('（A组）', '').replace('(A组)', '').strip()
            events.append((i, clean))
        elif events:
            # Use previous event name for merged cells
            events.append((i, None))
    return events


def parse_rows(rows, header_row):
    """Parse data rows for A组 format.

    Returns list of dicts:
    {
        'rank': int, 'district': str, 'name': str,
        'total_score': float, 'remark': str,
        'results': [{'event': str, 'raw_value': str, 'score': float}]
    }
    """
    events = parse_header(header_row)
    parsed = []

    for row in rows:
        if not row or len(row) < 5:
            continue

        rank_str = (row[0] or '').strip()
        if not rank_str or not rank_str.isdigit():
            continue

        name_raw = (row[2] or '').strip()
        score_raw = (row[3] or '').strip()

        # Handle column misalignment: long names can bleed into score column
        # e.g. name='EttoreColomb', score='o 98.5' -> name='EttoreColombo', score='98.5'
        if score_raw and not score_raw.replace('.', '').replace('-', '').isdigit():
            parts = score_raw.split()
            if len(parts) == 2:
                name_raw = name_raw + parts[0]
                score_raw = parts[1]
            else:
                # Try to extract number from end
                import re
                m = re.search(r'([\d.]+)$', score_raw)
                if m:
                    prefix = score_raw[:m.start()].strip()
                    name_raw = name_raw + prefix
                    score_raw = m.group(1)

        try:
            total_score = float(score_raw) if score_raw else None
        except ValueError:
            total_score = None

        record = {
            'rank': int(rank_str),
            'district': (row[1] or '').strip(),
            'name': name_raw,
            'total_score': total_score,
            'remark': (row[4] or '').strip() or None,
            'rating': None,
            'results': [],
        }

        if not record['name']:
            continue

        # Find which event has data
        for col_idx, event_name in events:
            if event_name is None:
                continue
            if col_idx + 1 >= len(row):
                continue
            raw = (row[col_idx] or '').strip()
            score_str = (row[col_idx + 1] or '').strip()
            if raw:
                score = float(score_str) if score_str else None
                record['results'].append({
                    'event': event_name,
                    'raw_value': raw,
                    'score': score,
                })

        parsed.append(record)

    return parsed
