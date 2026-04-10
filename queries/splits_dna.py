"""Cross-competition splits DNA profile for an athlete.

Aggregates all timed swimming results that carry per-50m split data for a
given participant, computes pacing metrics, classifies the athlete into an
"archetype" (前快 / 后劲 / 均衡 / 爆发), and renders the data needed by the
选手查询 page DNA block.

All heuristics are pure Python + pandas — no LLM.
"""

from __future__ import annotations

import json
import math
from typing import Optional

import pandas as pd
import streamlit as st

from db.connection import get_db
from queries.insights import _is_im, _generic_seg_labels, _laps_matrix


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def _parse_splits(s):
    if not s:
        return []
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return []


@st.cache_data(ttl=600)
def get_participant_splits(participant_id: int) -> pd.DataFrame:
    """Fetch all timed swimming results with non-empty splits for one athlete.

    Returns columns: competition, comp_short, comp_date, event_id, event_name,
    gender, group_name, numeric_value, status, splits (parsed list[dict]).
    """
    conn = get_db()
    df = pd.read_sql_query(
        """
        SELECT c.name           AS competition,
               c.short_name     AS comp_short,
               c.date           AS comp_date,
               ev.id            AS event_id,
               ev.name          AS event_name,
               g.gender         AS gender,
               g.group_name     AS group_name,
               r.numeric_value  AS numeric_value,
               r.status         AS status,
               r.splits         AS splits
        FROM enrollment e
        JOIN competition c ON c.id = e.competition_id
        JOIN group_def g   ON g.id = e.group_id
        JOIN result r      ON r.enrollment_id = e.id
        JOIN event ev      ON ev.id = r.event_id
        WHERE e.participant_id = ?
          AND ev.category = 'swimming'
          AND ev.result_type = 'time'
          AND r.status = 'normal'
          AND r.numeric_value IS NOT NULL
          AND r.splits IS NOT NULL
          AND r.splits != ''
        ORDER BY c.date, c.id, ev.sort_order
        """,
        conn,
        params=(participant_id,),
    )
    conn.close()

    if df.empty:
        return df
    df['splits'] = df['splits'].apply(_parse_splits)
    df = df[df['splits'].apply(lambda s: isinstance(s, list) and len(s) >= 2)]
    df = df.reset_index(drop=True)
    return df


@st.cache_data(ttl=600)
def get_peer_splits(
    event_name: str,
    gender: str,
    group_name: str,
    exclude_participant_id: Optional[int] = None,
) -> pd.DataFrame:
    """Return all peer splits for the same event + gender + group_name.

    We match by event NAME (not id) to allow cross-competition pooling when
    the same logical event has different row ids per competition. Group is
    matched by gender + group_name for the same reason (to allow athletes who
    crossed age bands between competitions to still contribute).
    """
    conn = get_db()
    params = [event_name, gender, group_name]
    sql = """
        SELECT r.splits
        FROM result r
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN group_def g  ON g.id = e.group_id
        JOIN event ev     ON ev.id = r.event_id
        WHERE ev.name = ?
          AND g.gender = ?
          AND g.group_name = ?
          AND ev.category = 'swimming'
          AND ev.result_type = 'time'
          AND r.status = 'normal'
          AND r.numeric_value IS NOT NULL
          AND r.splits IS NOT NULL
          AND r.splits != ''
    """
    if exclude_participant_id is not None:
        sql += " AND e.participant_id != ?"
        params.append(exclude_participant_id)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()

    if df.empty:
        return df
    df['splits'] = df['splits'].apply(_parse_splits)
    df = df[df['splits'].apply(lambda s: isinstance(s, list) and len(s) >= 2)]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Single-race metrics
# ---------------------------------------------------------------------------

def compute_race_metrics(splits: list[dict], is_im: bool) -> Optional[dict]:
    """Compute pacing metrics for a single race.

    Returns None if the race has fewer than 2 valid lap segments.
    """
    if not splits:
        return None
    laps = [s.get('lap') for s in splits]
    laps = [float(x) for x in laps if x is not None and not (isinstance(x, float) and math.isnan(x))]
    n = len(laps)
    if n < 2:
        return None

    first_lap = laps[0]
    last_lap = laps[-1]

    # Middle laps exclude start dive (first) and final sprint (last). CV is
    # only meaningful when we actually trim those bookend laps, so for n<4
    # we leave mid_cv as None.
    mid_cv: Optional[float] = None
    if n >= 4:
        mid_laps = laps[1:-1]
        mid_mean_inner = sum(mid_laps) / len(mid_laps)
        if len(mid_laps) > 1 and mid_mean_inner > 0:
            variance = sum((x - mid_mean_inner) ** 2 for x in mid_laps) / len(mid_laps)
            mid_std = math.sqrt(variance)
            mid_cv = mid_std / mid_mean_inner
        mid_mean = mid_mean_inner
    else:
        mid_mean = sum(laps) / n

    # F/B ratio — skip for IM, and require n>=4 so that dive-bonus on lap[0]
    # is diluted by at least one "normal" front lap. 100m (n=2) is excluded —
    # its lap[0] is dominated by the dive and the ratio is meaningless.
    fb_ratio: Optional[float] = None
    if not is_im and n >= 4:
        half = n // 2
        front = laps[:half]
        back = laps[half:]
        front_mean = sum(front) / len(front)
        back_mean = sum(back) / len(back)
        if back_mean > 0:
            fb_ratio = front_mean / back_mean

    # Fade index: last vs min of mid (how much fading at the end)
    mid_for_fade = laps[1:-1] if n >= 4 else laps
    min_mid = min(mid_for_fade)
    fade_index = (last_lap - min_mid) / min_mid if min_mid > 0 else 0.0

    return {
        'n_segs': n,
        'first_lap': first_lap,
        'last_lap': last_lap,
        'mid_mean': mid_mean,
        'mid_cv': mid_cv,
        'fb_ratio': fb_ratio,
        'fade_index': fade_index,
        'laps': laps,
    }


# ---------------------------------------------------------------------------
# Aggregate DNA
# ---------------------------------------------------------------------------

ARCHETYPES = {
    '前快型':  {'en': 'Front-Loaded', 'emoji': '🔥'},
    '后劲型':  {'en': 'Back-Loaded',  'emoji': '🚀'},
    '均衡型':  {'en': 'Even-Paced',   'emoji': '⚖️'},
    '爆发型':  {'en': 'Burst',        'emoji': '💥'},
}


def aggregate_dna(per_race_metrics: list[dict]) -> dict:
    """Aggregate per-race metrics into a single DNA profile."""
    n_races = len(per_race_metrics)
    non_im = [m for m in per_race_metrics if m.get('fb_ratio') is not None]
    n_non_im = len(non_im)

    fb_vals = [m['fb_ratio'] for m in non_im]
    cv_vals = [m['mid_cv'] for m in per_race_metrics if m.get('mid_cv') is not None]
    fade_vals = [m['fade_index'] for m in per_race_metrics if m.get('fade_index') is not None]

    avg_fb = (sum(fb_vals) / len(fb_vals)) if fb_vals else None
    avg_cv = (sum(cv_vals) / len(cv_vals)) if cv_vals else None
    avg_fade = (sum(fade_vals) / len(fade_vals)) if fade_vals else 0.0

    # Classification (priority order)
    # fb_ratio = front_mean / back_mean (only defined for n>=4 non-IM races)
    #   fb < 1 → front laps are faster (smaller time) → front-loaded
    #   fb > 1 → front laps are slower → back-loaded (negative split)
    # 爆发型 requires both irregular middle-pace AND front-loaded tendency.
    if (avg_cv is not None and avg_cv > 0.05
            and avg_fb is not None and avg_fb < 0.98):
        archetype = '爆发型'
    elif avg_fb is not None and avg_fb > 1.01:
        archetype = '后劲型'
    elif avg_fb is not None and avg_fb < 0.98:
        archetype = '前快型'
    else:
        archetype = '均衡型'

    meta = ARCHETYPES[archetype]
    return {
        'archetype': archetype,
        'archetype_en': meta['en'],
        'archetype_emoji': meta['emoji'],
        'avg_fb_ratio': avg_fb,
        'avg_cv': avg_cv,
        'avg_fade': avg_fade,
        'n_races': n_races,
        'n_non_im_races': n_non_im,
    }


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------

_NARRATIVES = {
    '前快型': "数据显示该选手是典型的 **前快型** 节奏 —— 前半程平均比后半程快 {pct:.1f}%，起始爆发力强但后程有衰减空间。训练建议：加强后半程的耐乳酸能力和节奏控制。",
    '后劲型': "这是相对少见的 **后劲型** 选手 —— 后半程平均比前半程快 {pct:.1f}%（负分段），配速控制和后程冲刺能力优秀。这种节奏在 200m+ 项目上容易打出突破性成绩。",
    '均衡型': "该选手的节奏非常 **均衡** —— 前后程差距仅 {pct:.1f}%，中间段变异系数 CV={cv:.3f}，属于最稳定的节奏类型。重点可放在整体速度上限的提升。",
    '爆发型': "该选手展现出 **爆发型** 特征 —— 出发段明显强于后续平均（CV={cv:.3f}），但波动偏大。可以加强匀速能力训练，把爆发力转化为可持续速度。",
}


def build_narrative(agg: dict, n_events: int) -> str:
    arche = agg['archetype']
    fb = agg.get('avg_fb_ratio')
    cv = agg.get('avg_cv')
    cv_display = cv if cv is not None else 0.0

    if arche == '前快型' and fb is not None:
        # fb < 1: front_mean < back_mean → front faster by (1 - fb)
        pct = (1.0 - fb) * 100
        text = _NARRATIVES[arche].format(pct=pct)
    elif arche == '后劲型' and fb is not None:
        # fb > 1: front_mean > back_mean → back faster by (fb - 1)
        pct = (fb - 1.0) * 100
        text = _NARRATIVES[arche].format(pct=pct)
    elif arche == '均衡型':
        pct = abs((fb - 1.0) * 100) if fb is not None else 0.0
        text = _NARRATIVES[arche].format(pct=pct, cv=cv_display)
    else:  # 爆发型
        text = _NARRATIVES[arche].format(cv=cv_display)

    suffix = f"\n\n*本画像基于 {agg['n_races']} 场有分段的比赛（共 {n_events} 个项目）聚合得出。*"
    if agg['n_races'] == 1:
        suffix = "\n\n*⚠️ 仅基于单场比赛，样本偏小，趋势判断仅供参考。*"
    return text + suffix


# ---------------------------------------------------------------------------
# Top-level entrypoint
# ---------------------------------------------------------------------------

def build_dna_profile(participant_id: int) -> Optional[dict]:
    """Build a complete DNA profile for an athlete.

    Returns None if there is no split data at all for this athlete.
    """
    df = get_participant_splits(participant_id)
    if df.empty:
        return None

    per_race_ui: list[dict] = []
    per_race_metrics: list[dict] = []

    for _, row in df.iterrows():
        splits = row['splits']
        is_im = _is_im(row['event_name'])
        metrics = compute_race_metrics(splits, is_im)
        if metrics is None:
            continue

        # Peer average lap curve
        peer_df = get_peer_splits(
            event_name=row['event_name'],
            gender=row['gender'],
            group_name=row['group_name'],
            exclude_participant_id=participant_id,
        )
        peer_avg_laps: Optional[list[float]] = None
        if len(peer_df) >= 3:
            n_segs = metrics['n_segs']
            peer_mat = _laps_matrix(peer_df, n_segs)
            col_means = peer_mat.mean(axis=0, skipna=True)
            if not col_means.isna().all():
                peer_avg_laps = [
                    None if pd.isna(v) else float(v) for v in col_means.tolist()
                ]

        seg_labels = _generic_seg_labels([splits], is_im)

        per_race_ui.append({
            'event_name': row['event_name'],
            'comp': row['comp_short'] or row['competition'],
            'comp_date': row['comp_date'] or '',
            'gender': row['gender'],
            'group_name': row['group_name'],
            'laps': metrics['laps'],
            'seg_labels': seg_labels,
            'peer_avg_laps': peer_avg_laps,
            'metrics': metrics,
        })
        per_race_metrics.append(metrics)

    if not per_race_metrics:
        return None

    agg = aggregate_dna(per_race_metrics)
    n_events = df['event_name'].nunique()
    narrative = build_narrative(agg, n_events)

    return {
        'has_data': True,
        'n_races': len(per_race_metrics),
        'n_events': n_events,
        'per_race': per_race_ui,
        'aggregate': agg,
        'narrative': narrative,
    }
