"""Relay lineup recommendation (排兵布阵).

Given a district + group + competition, find the optimal assignment of swimmers
to relay legs based on individual event times. Supports both "this competition"
and "historical PB" data sources, plus comparison with the actually-sent lineup.
"""

from __future__ import annotations

import itertools
import json

import pandas as pd

from db.connection import get_db

# FINA medley relay stroke order (leg 1-4)
MEDLEY_STROKE_ORDER = ['仰泳', '蛙泳', '蝶泳', '自由泳']

# IM single-event stroke order (from pdf_parser_final.py).
# NOTE: different from MEDLEY_STROKE_ORDER above — used to interpret 200/400 IM splits.
IM_STROKE_ORDER = ['蝶泳', '仰泳', '蛙泳', '自由泳']

# Empirical 50m / 100m time ratio — used as a fallback when only one distance
# is available. Real ratio varies by swimmer (0.47-0.50); 0.485 is a compromise.
# Note: this only affects recommendation *ordering* robustness, not truth.
CONV_100_TO_50 = 0.485
CONV_50_TO_100 = 1 / CONV_100_TO_50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_time(seconds) -> str:
    """Format seconds as M:SS.SS or SS.SS."""
    if seconds is None or (isinstance(seconds, float) and pd.isna(seconds)):
        return '—'
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f"{m}:{s:05.2f}"
    return f"{seconds:.2f}"


# Individual event name → (distance, stroke)
_INDIVIDUAL_EVENTS = {
    '50米自由泳': (50, '自由泳'), '100米自由泳': (100, '自由泳'),
    '50米仰泳': (50, '仰泳'), '100米仰泳': (100, '仰泳'),
    '50米蛙泳': (50, '蛙泳'), '100米蛙泳': (100, '蛙泳'),
    '50米蝶泳': (50, '蝶泳'), '100米蝶泳': (100, '蝶泳'),
}


def resolve_time(cell: dict, slot: tuple) -> tuple | None:
    """Best estimate for a (distance, stroke) slot.

    Priority chain:
      1. Exact-distance 单项 (individual event at the right distance)
      2. Other-distance 单项 (converted via 0.485 ratio; tagged '按Xm推算')
      3. Exact-distance 400个混分段 (best IM split option, since 400 IM splits are 100m)
      4. Exact-distance 200个混分段 (50m, but with fatigue caveat)
      5. Other-distance IM splits (converted, tagged with '推算')

    Returns (seconds, source_label) or None.
    """
    target_dist, stroke = slot
    other_dist = 100 if target_dist == 50 else 50
    exact_cell = cell.get(slot, {})
    other_cell = cell.get((other_dist, stroke), {})
    conv = CONV_100_TO_50 if target_dist == 50 else CONV_50_TO_100

    # 1. Exact single-event
    if '单项' in exact_cell:
        return (exact_cell['单项'], '单项')

    # 2. Other-distance single-event (converted — usually the best fallback
    #    since 100m times strongly predict 50m rankings, unlike fatigued IM splits)
    if '单项' in other_cell:
        return (other_cell['单项'] * conv, f'按{other_dist}米推算')

    # 3. Exact-distance IM splits
    for src in ['400个混分段', '200个混分段']:
        if src in exact_cell:
            return (exact_cell[src], src)

    # 4. Other-distance IM splits (last-ditch)
    for src in ['400个混分段', '200个混分段']:
        if src in other_cell:
            return (other_cell[src] * conv, f'{src}推算')

    return None


# ---------------------------------------------------------------------------
# Build swimmer → stroke time table
# ---------------------------------------------------------------------------

def build_swimmer_table(
    competition_id: int, gender: str, group_name: str, district: str,
    source: str = 'this_comp',
) -> dict:
    """Build a swimmer stroke-time lookup for a district in a group.

    Args:
        source: 'this_comp' (only the specified competition) or
                'historical_pb' (min across all competitions for each swimmer).

    Returns:
        dict {(name, district): {(distance, stroke): {source_label: min_seconds}}}
        Only includes swimmers enrolled in the specified (competition, gender, group).
    """
    conn = get_db()

    if source == 'this_comp':
        sql = """
            SELECT p.name, p.district, ev.name AS event_name,
                   r.numeric_value, r.splits
            FROM result r
            JOIN enrollment e ON e.id = r.enrollment_id
            JOIN participant p ON p.id = e.participant_id
            JOIN group_def g ON g.id = e.group_id
            JOIN event ev ON ev.id = r.event_id
            WHERE e.competition_id = ?
              AND g.gender = ? AND g.group_name = ?
              AND p.district = ?
              AND ev.category = 'swimming'
              AND r.status = 'normal'
              AND r.numeric_value IS NOT NULL
        """
        params = (competition_id, gender, group_name, district)
    else:  # historical_pb
        # All swim results for participants who ARE in the target (comp, group, district),
        # across every competition they've ever appeared in. Aggregation (min) happens
        # later when we write into the per-source dict.
        sql = """
            SELECT p.name, p.district, ev.name AS event_name,
                   r.numeric_value, r.splits
            FROM result r
            JOIN enrollment e ON e.id = r.enrollment_id
            JOIN participant p ON p.id = e.participant_id
            JOIN event ev ON ev.id = r.event_id
            WHERE ev.category = 'swimming'
              AND r.status = 'normal'
              AND r.numeric_value IS NOT NULL
              AND p.id IN (
                  SELECT p2.id FROM participant p2
                  JOIN enrollment e2 ON e2.participant_id = p2.id
                  JOIN group_def g2 ON g2.id = e2.group_id
                  WHERE e2.competition_id = ?
                    AND g2.gender = ? AND g2.group_name = ?
                    AND p2.district = ?
              )
        """
        params = (competition_id, gender, group_name, district)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    table: dict = {}

    def _add(swimmer_key, slot, src, seconds):
        if seconds is None:
            return
        cell = table.setdefault(swimmer_key, {})
        slot_dict = cell.setdefault(slot, {})
        if src not in slot_dict or seconds < slot_dict[src]:
            slot_dict[src] = seconds

    for name, p_district, ev_name, num_val, splits_json in rows:
        swimmer_key = (name, p_district)

        # 1. Individual event
        if ev_name in _INDIVIDUAL_EVENTS:
            slot = _INDIVIDUAL_EVENTS[ev_name]
            _add(swimmer_key, slot, '单项', num_val)
            continue

        # 2. IM splits (200 or 400 个人混合泳)
        if ('个人混合泳' in ev_name or '个混' in ev_name) and splits_json:
            try:
                splits = json.loads(splits_json)
            except (json.JSONDecodeError, TypeError):
                continue
            if not splits:
                continue

            if '200' in ev_name:
                src_label = '200个混分段'
                lap_dist = 50
            elif '400' in ev_name:
                src_label = '400个混分段'
                lap_dist = 100
            else:
                continue

            for i, seg in enumerate(splits):
                lap = seg.get('lap')
                if lap is None:
                    continue
                stroke = seg.get('stroke')
                if not stroke:
                    # Fall back to computed IM order (butterfly, back, breast, free)
                    stroke = IM_STROKE_ORDER[min(i, 3)]
                _add(swimmer_key, (lap_dist, stroke), src_label, lap)

    return table


# ---------------------------------------------------------------------------
# Recommend lineups
# ---------------------------------------------------------------------------

def recommend_medley_relay(swimmer_table: dict, leg_distance: int) -> dict:
    """Assign 4 distinct swimmers to 4 strokes to minimize total time.

    Args:
        leg_distance: 50 (for 4×50) or 100 (for 4×100)

    Returns dict with:
        - lineup: [{'leg_order', 'stroke', 'swimmer_name', 'district',
                    'est_seconds', 'source'}] × 4, ordered by leg_order
        - total_seconds: float
        - warnings: list[str]
    """
    candidates = []  # (name, district, {stroke: (seconds, source)})
    for (name, district), cell in swimmer_table.items():
        stroke_times = {}
        for stroke in MEDLEY_STROKE_ORDER:
            res = resolve_time(cell, (leg_distance, stroke))
            if res is not None:
                stroke_times[stroke] = res
        if stroke_times:
            candidates.append((name, district, stroke_times))

    warnings: list[str] = []
    if len(candidates) < 4:
        return {
            'lineup': [],
            'total_seconds': None,
            'warnings': [f'候选不足：仅有 {len(candidates)} 名有 {leg_distance}m '
                         f'泳姿数据的选手，需要 4 名。'],
        }

    # Check if any 4-swimmer combo can cover all 4 strokes at all
    all_strokes_available: set = set()
    for _, _, st in candidates:
        all_strokes_available.update(st.keys())
    missing_strokes = [s for s in MEDLEY_STROKE_ORDER if s not in all_strokes_available]
    if missing_strokes:
        return {
            'lineup': [],
            'total_seconds': None,
            'warnings': [f'无可用数据的泳姿：{"、".join(missing_strokes)}。无法组成完整混合泳接力阵容。'],
        }

    # Brute-force optimization
    best_total = float('inf')
    best_assignment: tuple | None = None
    n = len(candidates)

    for combo in itertools.combinations(range(n), 4):
        for perm in itertools.permutations(range(4)):
            # perm[i] = stroke index assigned to combo[i]
            total = 0.0
            valid = True
            for i, stroke_idx in enumerate(perm):
                stroke = MEDLEY_STROKE_ORDER[stroke_idx]
                st_dict = candidates[combo[i]][2]
                if stroke not in st_dict:
                    valid = False
                    break
                total += st_dict[stroke][0]
            if valid and total < best_total:
                best_total = total
                best_assignment = (combo, perm)

    if best_assignment is None:
        return {
            'lineup': [],
            'total_seconds': None,
            'warnings': ['无法组成完整阵容：没有候选组合覆盖全部 4 种泳姿。'],
        }

    combo, perm = best_assignment
    lineup: list = [None] * 4
    for i, stroke_idx in enumerate(perm):
        swimmer = candidates[combo[i]]
        stroke = MEDLEY_STROKE_ORDER[stroke_idx]
        t, src = swimmer[2][stroke]
        lineup[stroke_idx] = {
            'leg_order': stroke_idx + 1,
            'stroke': stroke,
            'swimmer_name': swimmer[0],
            'district': swimmer[1],
            'est_seconds': t,
            'source': src,
        }

    return {
        'lineup': lineup,
        'total_seconds': best_total,
        'warnings': warnings,
    }


def recommend_free_relay(swimmer_table: dict, leg_distance: int) -> dict:
    """Pick the 4 fastest freestylers at the given leg distance."""
    candidates = []
    for (name, district), cell in swimmer_table.items():
        res = resolve_time(cell, (leg_distance, '自由泳'))
        if res is not None:
            t, src = res
            candidates.append((name, district, t, src))

    candidates.sort(key=lambda x: x[2])

    if len(candidates) < 4:
        return {
            'lineup': [],
            'total_seconds': None,
            'warnings': [f'候选不足：仅有 {len(candidates)} 名有 {leg_distance}m '
                         f'自由泳数据的选手，需要 4 名。'],
        }

    top4 = candidates[:4]
    lineup = []
    for i, (name, district, t, src) in enumerate(top4):
        lineup.append({
            'leg_order': i + 1,
            'stroke': '自由泳',
            'swimmer_name': name,
            'district': district,
            'est_seconds': t,
            'source': src,
        })

    return {
        'lineup': lineup,
        'total_seconds': sum(c[2] for c in top4),
        'warnings': [],
    }


# ---------------------------------------------------------------------------
# Actual relay lookup
# ---------------------------------------------------------------------------

def get_actual_relay(
    competition_id: int, gender: str, group_name: str,
    event_name: str, district: str,
) -> dict | None:
    """Return the actual lineup a district sent for a relay event, or None."""
    from queries.results import get_relay_results
    teams_df, legs_df = get_relay_results(competition_id, gender, group_name, event_name)
    if teams_df.empty:
        return None
    team_rows = teams_df[teams_df['district'] == district]
    if team_rows.empty:
        return None
    team = team_rows.iloc[0]
    team_legs = legs_df[legs_df['team_id'] == team['team_id']].sort_values('leg_order')

    is_medley = '混合泳' in event_name
    lineup = []
    for _, leg in team_legs.iterrows():
        if is_medley and 1 <= int(leg['leg_order']) <= 4:
            stroke = MEDLEY_STROKE_ORDER[int(leg['leg_order']) - 1]
        else:
            stroke = '自由泳'
        lineup.append({
            'leg_order': int(leg['leg_order']),
            'stroke': stroke,
            'swimmer_name': leg['swimmer_name'],
            'district': district,
            'actual_seconds': leg['leg_seconds'] if pd.notna(leg['leg_seconds']) else None,
            'cumulative_seconds': leg['cumulative_seconds'] if pd.notna(leg['cumulative_seconds']) else None,
        })

    return {
        'lineup': lineup,
        'total_seconds': team['final_seconds'] if pd.notna(team['final_seconds']) else None,
        'final_time': team['final_time'] or '',
        'rank': int(team['rank']) if pd.notna(team['rank']) else None,
        'status': team['status'] if pd.notna(team['status']) else 'normal',
    }
