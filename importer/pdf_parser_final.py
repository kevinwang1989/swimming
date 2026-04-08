"""Parser for the 2025 Shanghai Swimming Finals result booklet.

Format differs completely from v1.0 PDFs:
- Tables are organized per-event (one table per event) instead of per-group
- Includes segment times (分段成绩), reaction time (R.T.), and athlete level
- Long-distance events (>200m) split each athlete across multiple text lines

Parsing strategy:
- Use pdfplumber.extract_words() with x0 >= 0 to drop a mirrored-glyph artifact
- Group words into rows by y-coordinate
- Dedupe doubled chars on title lines
- Detect event titles, then parse main rows + continuation lap/cum rows via state machine
- Dedupe athletes by (event, name, district) to handle pages that re-print rows
"""

import re
from collections import defaultdict
from typing import Optional

import pdfplumber

# After dedup, matches e.g. "男子A组100米自由泳决赛成绩"
EVENT_TITLE_RE = re.compile(
    r'^(男|女)子([A-F])组(\d+(?:[Xx]\d+)?)米([^决预]+?)(决|预)赛成绩$'
)

LEVEL_TOKENS = {'一级', '二级', '三级', '无等级', '外籍'}
NON_NORMAL_REMARKS = {'DSQ', 'DNS', '弃权', '犯规', '放弃'}
IM_STROKE_ORDER = ['蝶泳', '仰泳', '蛙泳', '自由泳']


def dedupe_doubled(text: str) -> str:
    """Collapse doubled glyphs: 'AA' -> 'A', '110000' -> '100'.

    Title text in this PDF is rendered with each glyph drawn twice; folding
    pairs recovers the original. Safe for Chinese + digits in event titles.
    """
    return re.sub(r'(.)\1', r'\1', text)


def parse_time_to_seconds(s: str) -> Optional[float]:
    """Parse '24.33', '50.86', '1:36.48', '2:05.48' into seconds."""
    s = s.strip()
    m = re.match(r'^(\d+):(\d{1,2})\.(\d{1,2})$', s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 100.0
    if re.match(r'^\d+\.\d{1,2}$', s):
        return float(s)
    return None


def _is_time(tok: str) -> bool:
    return parse_time_to_seconds(tok) is not None


def segment_count(distance: int) -> int:
    """Number of 50m segments in an event of given total distance."""
    if distance <= 50:
        return 1
    return distance // 50


def im_stroke_for_segment(seg_idx: int, n_segs: int) -> str:
    """For an IM event, return stroke for the given 0-based segment index."""
    segs_per_stroke = max(n_segs // 4, 1)
    return IM_STROKE_ORDER[min(seg_idx // segs_per_stroke, 3)]


def _extract_rows(page) -> list:
    """Extract logical rows: list of (y, tokens). Drops mirrored negative-x content."""
    words = [w for w in page.extract_words() if w['x0'] >= 0]
    by_y = defaultdict(list)
    for w in words:
        by_y[round(w['top'])].append(w)
    # Merge near-equal y bins (±1)
    keys = sorted(by_y.keys())
    merged = []
    for yk in keys:
        if merged and yk - merged[-1][0] <= 1:
            merged[-1][1].extend(by_y[yk])
        else:
            merged.append([yk, list(by_y[yk])])
    rows = []
    for yk, ws in merged:
        ws.sort(key=lambda w: w['x0'])
        rows.append((yk, [w['text'] for w in ws]))
    return rows


def _split_leading_nums(tokens):
    nums = []
    i = 0
    while i < len(tokens) and tokens[i].isdigit():
        nums.append(int(tokens[i]))
        i += 1
    return nums, tokens[i:]


def _parse_main_row(tokens, n_segs_in_main):
    """Parse the first line of an athlete row.

    Layout: [rank?] heat lane name_parts... district [RT] cum_1..cum_K final [score] [level] [remark]
    where K = min(n_segs, 4) for multi-line events, else K = n_segs.
    Returns dict or None if doesn't look like an athlete row.
    """
    nums, rest = _split_leading_nums(tokens)
    if len(nums) < 2:
        return None

    # Walk through Chinese name/district until we hit a numeric token
    i = 0
    while i < len(rest) and not _is_time(rest[i]) and not re.match(r'^0\.\d{2}$', rest[i]):
        i += 1
    chinese_part = rest[:i]
    data_part = rest[i:]
    if len(chinese_part) < 1 or not data_part:
        return None

    district = chinese_part[-1]
    name = ''.join(chinese_part[:-1]) if len(chinese_part) >= 2 else chinese_part[0]
    if not name or not district:
        return None

    # heat/lane = last 2 nums; rank = optional preceding num
    if len(nums) >= 3:
        rank = nums[0]
        heat, lane = nums[-2], nums[-1]
    else:
        rank = None
        heat, lane = nums[0], nums[1]

    # Optional RT: token of form 0.xx (1 decimal digit also acceptable)
    rt = None
    if data_part and re.match(r'^0\.\d{1,2}$', data_part[0]):
        try:
            rt = float(data_part[0])
            data_part = data_part[1:]
        except ValueError:
            pass

    # Collect cumulative time tokens (up to n_segs_in_main)
    cums = []
    while data_part and _is_time(data_part[0]) and len(cums) < n_segs_in_main:
        cums.append(data_part[0])
        data_part = data_part[1:]
    if len(cums) < n_segs_in_main:
        return None

    # Final time: next time token (only present in main row when n_segs_in_main = total n_segs)
    final_time = None
    if data_part and _is_time(data_part[0]):
        final_time = data_part[0]
        data_part = data_part[1:]

    # Optional score: a numeric token like 11.0, 9.5 — distinguished from cum because
    # it sits after the final and is followed by a level token
    score = None
    if (data_part and re.match(r'^\d+(\.\d+)?$', data_part[0])
            and len(data_part) >= 2 and data_part[1] in LEVEL_TOKENS):
        try:
            score = float(data_part[0])
            data_part = data_part[1:]
        except ValueError:
            pass

    level = None
    if data_part and data_part[0] in LEVEL_TOKENS:
        level = data_part[0]
        data_part = data_part[1:]

    remark = ' '.join(data_part).strip() or None

    return {
        'rank': rank, 'heat': heat, 'lane': lane,
        'name': name, 'district': district,
        'rt': rt, 'cums': cums, 'final_time': final_time,
        'score': score, 'level': level, 'remark': remark,
        'status': 'normal',
        'laps': [cums[0]] if cums else [],  # lap1 == cum1
    }


def _parse_status_row(tokens):
    """DSQ / DNS / 弃权 / 犯规 / 放弃 row.

    Some rows (e.g. ending in 放弃) still carry full time data; we walk past
    Chinese name/district then drop the trailing numeric noise.
    """
    if not tokens or tokens[-1] not in NON_NORMAL_REMARKS:
        return None
    last = tokens[-1]
    body = tokens[:-1]
    nums, rest = _split_leading_nums(body)
    if len(nums) < 2:
        return None
    # Walk Chinese tokens until first time/RT-like token
    i = 0
    while i < len(rest) and not _is_time(rest[i]) and not re.match(r'^0\.\d{1,2}$', rest[i]):
        i += 1
    chinese_part = rest[:i] if i > 0 else rest
    if len(chinese_part) < 2:
        return None
    if len(nums) >= 3:
        rank = nums[0]
        heat, lane = nums[-2], nums[-1]
    else:
        rank = None
        heat, lane = nums[0], nums[1]
    district = chinese_part[-1]
    name = ''.join(chinese_part[:-1])
    if not name or not district:
        return None
    status = 'foul' if last in ('DSQ', '犯规') else 'withdrew'
    return {
        'rank': rank, 'heat': heat, 'lane': lane,
        'name': name, 'district': district,
        'rt': None, 'cums': [], 'final_time': None,
        'score': None, 'level': None, 'remark': last,
        'status': status, 'laps': [],
    }


def _all_time_tokens(tokens):
    return bool(tokens) and all(_is_time(t) for t in tokens)


def build_splits(rec, n_segs, event_name):
    """Build splits JSON list from rec['cums'] and rec['laps']."""
    is_im = '个人混合泳' in event_name
    splits = []
    cums = rec.get('cums') or []
    laps = rec.get('laps') or []
    for i in range(n_segs):
        cum_s = parse_time_to_seconds(cums[i]) if i < len(cums) else None
        lap_s = parse_time_to_seconds(laps[i]) if i < len(laps) else None
        splits.append({
            'dist': (i + 1) * 50,
            'cum': cum_s,
            'lap': lap_s,
            'stroke': im_stroke_for_segment(i, n_segs) if is_im else None,
        })
    return splits


def _looks_like_relay_team_header(tokens):
    """Relay team header: leading digits, then a Chinese district, then 1-2 numeric/time tokens.

    Examples:
        ['1', '1', '5', '普陀区', '3:29.10', '11.0']  -> rank=1, heat=1, lane=5
        ['1', '7', '虹口区', '3:50.33']                -> no rank, heat=1, lane=7
    """
    nums, rest = _split_leading_nums(tokens)
    if len(nums) < 2 or not rest:
        return None
    district = rest[0]
    if not district or district[0].isdigit() or _is_time(district):
        return None
    tail = rest[1:]
    if not tail or not _is_time(tail[0]):
        return None
    final_time = tail[0]
    score = None
    if len(tail) >= 2:
        try:
            score = float(tail[1])
        except ValueError:
            score = None
    if len(nums) >= 3:
        rank, heat, lane = nums[0], nums[-2], nums[-1]
    else:
        rank = None
        heat, lane = nums[0], nums[1]
    return {
        'rank': rank, 'heat': heat, 'lane': lane,
        'district': district,
        'final_time': final_time,
        'final_seconds': parse_time_to_seconds(final_time),
        'total_score': score,
        'athlete_level': None,
        'status': 'normal',
        'remark': None,
        'legs': [],
    }


def _parse_relay_leg(tokens, leg_order, splits_per_leg):
    """Relay leg row: [name, RT?, split_1, ..., split_K, cum, level?]."""
    if not tokens or tokens[0].isdigit():
        return None
    # Walk past Chinese name tokens until first numeric/time token
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if re.match(r'^0\.\d{1,2}$', t) or _is_time(t):
            break
        i += 1
    if i == 0 or i >= len(tokens):
        return None
    name = ''.join(tokens[:i])
    rest = tokens[i:]

    # Optional RT
    rt = None
    if rest and re.match(r'^0\.\d{1,2}$', rest[0]):
        try:
            rt = float(rest[0])
            rest = rest[1:]
        except ValueError:
            pass

    # Need splits_per_leg split times + 1 cum time
    needed = splits_per_leg + 1
    if len(rest) < needed:
        return None
    times = rest[:needed]
    if not all(_is_time(t) for t in times):
        return None
    splits = times[:splits_per_leg]
    cum = times[splits_per_leg]
    rest = rest[needed:]

    level = None
    if rest and rest[0] in LEVEL_TOKENS:
        level = rest[0]

    return {
        'order': leg_order,
        'name': name,
        'rt': rt,
        'splits': splits,         # list of split times within this leg
        'split_50': splits[0] if splits else None,
        'split_100': splits[1] if len(splits) > 1 else None,
        'cum': cum,
        'cum_seconds': parse_time_to_seconds(cum),
        'level': level,
    }


def parse_final_pdf(pdf_path: str) -> dict:
    """Parse the 2025 finals PDF.

    Returns:
        {
            'events': {(gender, group_name, event_name): [record, ...]},
            'relays': {(gender, group_name, event_name): [team, ...]},
        }
    """
    events_data = defaultdict(list)
    relays_data = defaultdict(list)
    seen_keys = set()  # (gender, group, event, name, district)
    seen_relay_keys = set()  # (gender, group, event, district)

    current_event = None  # (gender, group, event_name, n_segs)
    current_kind = None   # 'individual' | 'relay'
    pending = None        # athlete record currently collecting continuation rows
    pending_state = None  # 'first_lap' | 'cum_group' | 'lap_group' | None
    pending_team = None   # relay team currently collecting legs
    nonlocal_relay_leg_dist = [100]  # mutable cell to share with closures

    def flush_pending():
        nonlocal pending, pending_state
        if pending is None or current_event is None:
            pending = None
            pending_state = None
            return
        gender, group_name, event_name, n_segs = current_event
        key = (gender, group_name, event_name, pending['name'], pending['district'])
        if key not in seen_keys:
            seen_keys.add(key)
            pending['splits'] = build_splits(pending, n_segs, event_name)
            events_data[(gender, group_name, event_name)].append(pending)
        pending = None
        pending_state = None

    def flush_pending_team():
        nonlocal pending_team
        if pending_team is None or current_event is None:
            pending_team = None
            return
        gender, group_name, event_name, _n_segs = current_event
        key = (gender, group_name, event_name, pending_team['district'])
        if key not in seen_relay_keys:
            seen_relay_keys.add(key)
            # athlete_level taken from leg 1 if available
            if pending_team['legs']:
                pending_team['athlete_level'] = pending_team['legs'][0].get('level')
                # Compute leg_time per leg (cum diff)
                prev_cum = 0.0
                for leg in pending_team['legs']:
                    cs = leg.get('cum_seconds')
                    if cs is None:
                        leg['leg_seconds'] = None
                        leg['leg_time'] = None
                    else:
                        leg['leg_seconds'] = cs - prev_cum
                        leg['leg_time'] = leg['cum'] if leg['order'] == 1 else None
                        prev_cum = cs
            relays_data[(gender, group_name, event_name)].append(pending_team)
        pending_team = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for yk, tokens in _extract_rows(page):
                if not tokens:
                    continue
                joined = ''.join(tokens)

                # Skip running header (year line)
                if '2025年' in joined or '22002255' in joined:
                    continue
                # Pure separator
                if all(c in '=-' for c in joined):
                    continue
                # Lone page number
                if len(tokens) == 1 and tokens[0].isdigit() and len(tokens[0]) <= 3:
                    continue

                # Event title?
                dedup = dedupe_doubled(joined)
                m = EVENT_TITLE_RE.match(dedup)
                if m:
                    flush_pending()
                    flush_pending_team()
                    gender = m.group(1)
                    group_name = m.group(2)
                    distance_str = m.group(3)
                    stroke = m.group(4)
                    # Relay distances rendered as e.g. "4X100" (after dedupe of "44XX110000")
                    relay_m = re.match(r'^(\d+)[Xx](\d+)$', distance_str)
                    if relay_m or '接力' in stroke:
                        if relay_m:
                            legs_n = int(relay_m.group(1))
                            leg_dist = int(relay_m.group(2))
                            event_name = f'{legs_n}X{leg_dist}米{stroke}'
                        else:
                            event_name = f'{distance_str}米{stroke}'
                            legs_n = 4
                            leg_dist = 100
                        # n_segs encodes legs_n; leg_dist tracked via current_relay_leg_dist
                        current_event = (gender, group_name, event_name, legs_n)
                        current_kind = 'relay'
                        nonlocal_relay_leg_dist[0] = leg_dist
                        continue
                    distance = int(distance_str)
                    event_name = f'{distance}米{stroke}'
                    current_event = (gender, group_name, event_name, segment_count(distance))
                    current_kind = 'individual'
                    continue

                # Column header rows (e.g. "名次 组次 泳道 姓名 ...") and the
                # second header line of long events ("250m 300m 350m 400m")
                if tokens[0] == '名次' or '名次' in tokens[:3]:
                    continue
                if all(re.match(r'^\d+m$', t) for t in tokens):
                    continue

                if current_event is None:
                    continue

                gender, group_name, event_name, n_segs = current_event

                # ----- Relay branch -----
                if current_kind == 'relay':
                    # Try team header
                    team = _looks_like_relay_team_header(tokens)
                    if team is not None:
                        flush_pending_team()
                        pending_team = team
                        continue
                    # Otherwise try a leg row
                    if pending_team is not None and len(pending_team['legs']) < n_segs:
                        leg_idx = len(pending_team['legs']) + 1
                        splits_per_leg = max(1, nonlocal_relay_leg_dist[0] // 50)
                        leg = _parse_relay_leg(tokens, leg_idx, splits_per_leg)
                        if leg is not None:
                            pending_team['legs'].append(leg)
                            if len(pending_team['legs']) >= n_segs:
                                flush_pending_team()
                    continue

                # Multi-line continuation? Only when pending is collecting more data
                if pending is not None and pending_state is not None and _all_time_tokens(tokens):
                    if pending_state == 'first_lap':
                        # Expect 3 lap tokens (laps 2..min(4, n_segs))
                        for t in tokens:
                            pending['laps'].append(t)
                        if n_segs <= 4:
                            flush_pending()
                        else:
                            pending_state = 'cum_group'
                        continue
                    if pending_state == 'cum_group':
                        for t in tokens:
                            pending['cums'].append(t)
                        pending_state = 'lap_group'
                        continue
                    if pending_state == 'lap_group':
                        for t in tokens:
                            pending['laps'].append(t)
                        if len(pending['cums']) >= n_segs:
                            flush_pending()
                        else:
                            pending_state = 'cum_group'
                        continue

                # Status row (DSQ / DNS / etc.)
                if tokens[-1] in NON_NORMAL_REMARKS:
                    flush_pending()
                    rec = _parse_status_row(tokens)
                    if rec:
                        pending = rec
                        pending_state = None  # nothing more to collect
                        flush_pending()
                    continue

                # Main row
                n_segs_in_main = min(4, n_segs)
                rec = _parse_main_row(tokens, n_segs_in_main)
                if rec is None:
                    continue

                # New main row → flush previous pending first
                flush_pending()
                pending = rec
                if n_segs == 1:
                    flush_pending()
                else:
                    pending_state = 'first_lap'

        # End of pdf
        flush_pending()
        flush_pending_team()

    return {'events': dict(events_data), 'relays': dict(relays_data)}
