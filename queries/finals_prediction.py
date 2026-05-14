"""Finals (总决赛) prediction from the two 2026 qualifying stations.

Qualification rule (computed per group):
  - Path A: 第一站 overall ranking top 30%  (enrollment.rank <= round(N * 0.30))
  - Path B: 第二站 per-event top 10
  - Qualified set = union of A and B by participant_id

Prediction rule:
  - Predicted time = PB across the two stations (min numeric_value per event)
  - Per (group, event): qualified athletes sorted by PB; the 16th = cutoff line
"""

import pandas as pd
import streamlit as st

from db.connection import get_db

STATION_1 = '第一站'
STATION_2 = '第二站'
PATH_A_PCT = 0.30
PATH_B_TOP_N = 10
FINALS_CUTOFF_RANK = 16

# 男A/女A swam 200m IM under the legacy name "200米混合泳" at 第一站 only;
# every other group + 第二站 use the canonical "200米个人混合泳".
EVENT_NAME_MAP = {'200米混合泳': '200米个人混合泳'}


def _norm_event(name: str) -> str:
    return EVENT_NAME_MAP.get(name, name)


@st.cache_data(ttl=600)
def get_station_results() -> pd.DataFrame:
    """All normal swimming/time results from 第一站 + 第二站.

    Columns: participant_id, name, district, gender, group_name, group_label,
             station, event, sort_order, numeric_value, enrollment_rank
    """
    conn = get_db()
    df = pd.read_sql_query(
        """
        SELECT p.id            AS participant_id,
               p.name          AS name,
               p.district      AS district,
               g.gender        AS gender,
               g.group_name    AS group_name,
               c.short_name    AS station,
               ev.name         AS event_name,
               ev.sort_order   AS sort_order,
               r.numeric_value AS numeric_value,
               e.rank          AS enrollment_rank
        FROM result r
        JOIN enrollment e   ON e.id = r.enrollment_id
        JOIN participant p  ON p.id = e.participant_id
        JOIN group_def g    ON g.id = e.group_id
        JOIN competition c  ON c.id = e.competition_id
        JOIN event ev       ON ev.id = r.event_id
        WHERE c.short_name IN (?, ?)
          AND r.status = 'normal'
          AND r.numeric_value IS NOT NULL
          AND r.numeric_value > 0
          AND ev.category = 'swimming'
          AND ev.result_type = 'time'
        """,
        conn,
        params=(STATION_1, STATION_2),
    )
    conn.close()

    if df.empty:
        return df
    df['event'] = df['event_name'].map(_norm_event)
    df['group_label'] = df['gender'] + df['group_name']
    return df


@st.cache_data(ttl=600)
def get_group_enrollment_counts() -> dict:
    """第一站 enrollment count per group_label — used for the Path A threshold."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT g.gender || g.group_name AS group_label, COUNT(*) AS n
        FROM enrollment e
        JOIN group_def g   ON g.id = e.group_id
        JOIN competition c ON c.id = e.competition_id
        WHERE c.short_name = ?
        GROUP BY g.gender, g.group_name
        """,
        (STATION_1,),
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def compute_qualifiers(results_df: pd.DataFrame, counts: dict) -> pd.DataFrame:
    """Union of Path A and Path B qualifiers, one row per qualified athlete.

    Columns: participant_id, name, district, group_label, paths (list[str]),
             path_a (bool), path_b (bool), enrollment_rank (第一站, may be NaN)
    """
    if results_df.empty:
        return pd.DataFrame()

    s1 = results_df[results_df['station'] == STATION_1]
    s2 = results_df[results_df['station'] == STATION_2]

    # reasons[participant_id] = {'group_label':..., 'name':..., 'district':...,
    #                            'paths': [...], 'path_a': bool, 'path_b': bool,
    #                            'enrollment_rank': int|None}
    reasons: dict[int, dict] = {}

    def _ensure(pid, row):
        if pid not in reasons:
            reasons[pid] = {
                'participant_id': pid,
                'name': row['name'],
                'district': row['district'],
                'group_label': row['group_label'],
                'paths': [],
                'path_a': False,
                'path_b': False,
                'enrollment_rank': None,
            }
        return reasons[pid]

    # ---- Path A: 第一站 overall top 30% per group ----
    # One enrollment_rank per (participant, group) — dedup first.
    s1_ranks = (
        s1[['participant_id', 'name', 'district', 'group_label', 'enrollment_rank']]
        .drop_duplicates('participant_id')
    )
    for group_label, grp in s1_ranks.groupby('group_label'):
        n = counts.get(group_label, len(grp))
        threshold = round(n * PATH_A_PCT)
        for _, row in grp.iterrows():
            rank = row['enrollment_rank']
            if pd.notna(rank):
                rec = _ensure(row['participant_id'], row)
                rec['enrollment_rank'] = int(rank)
                if rank <= threshold:
                    rec['path_a'] = True
                    rec['paths'].append(f"第一站综合第{int(rank)}名（前30%）")

    # ---- Path B: 第二站 per-event top 10 ----
    for (group_label, event), grp in s2.groupby(['group_label', 'event']):
        # ordinal rank by time; ties broken arbitrarily but min method keeps
        # boundary ties inclusive
        ranked = grp.sort_values('numeric_value').reset_index(drop=True)
        ranked['event_rank'] = ranked['numeric_value'].rank(method='min').astype(int)
        top = ranked[ranked['event_rank'] <= PATH_B_TOP_N]
        for _, row in top.iterrows():
            rec = _ensure(row['participant_id'], row)
            rec['path_b'] = True
            rec['paths'].append(f"第二站·{event}·第{int(row['event_rank'])}名")

    if not reasons:
        return pd.DataFrame()

    out = pd.DataFrame(list(reasons.values()))
    # Only keep athletes who actually qualified via at least one path
    out = out[out['path_a'] | out['path_b']].reset_index(drop=True)
    return out


def compute_event_predictions(results_df: pd.DataFrame,
                              qualifiers_df: pd.DataFrame) -> pd.DataFrame:
    """For each (qualified athlete, event): PB across both stations.

    Columns: group_label, event, sort_order, participant_id, name, district,
             pb_seconds, pb_station, predicted_rank
    """
    if results_df.empty or qualifiers_df.empty:
        return pd.DataFrame()

    qualified_ids = set(qualifiers_df['participant_id'])
    qres = results_df[results_df['participant_id'].isin(qualified_ids)].copy()
    if qres.empty:
        return pd.DataFrame()

    # PB per (participant, event): min numeric_value. On a cross-station tie we
    # prefer 第二站 — sort so 第二站 sorts first within equal times.
    qres['_station_pref'] = (qres['station'] == STATION_2).map({True: 0, False: 1})
    qres = qres.sort_values(['numeric_value', '_station_pref'])

    pb = (
        qres.groupby(['group_label', 'event', 'participant_id'], as_index=False)
        .agg(
            name=('name', 'first'),
            district=('district', 'first'),
            sort_order=('sort_order', 'first'),
            pb_seconds=('numeric_value', 'first'),
            pb_station=('station', 'first'),
        )
    )

    pb['predicted_rank'] = (
        pb.groupby(['group_label', 'event'])['pb_seconds']
        .rank(method='min')
        .astype(int)
    )
    pb = pb.sort_values(['group_label', 'sort_order', 'predicted_rank']).reset_index(drop=True)
    return pb


def compute_event_cutoffs(predictions_df: pd.DataFrame) -> pd.DataFrame:
    """Per (group, event): the 16th-place cutoff time, or insufficient flag.

    Columns: group_label, event, sort_order, n_qualified, cutoff_seconds,
             insufficient (bool)
    """
    if predictions_df.empty:
        return pd.DataFrame()

    rows = []
    for (group_label, event), grp in predictions_df.groupby(['group_label', 'event']):
        n = len(grp)
        sort_order = grp['sort_order'].iloc[0]
        if n >= FINALS_CUTOFF_RANK:
            cutoff = grp.sort_values('pb_seconds')['pb_seconds'].iloc[FINALS_CUTOFF_RANK - 1]
            rows.append({
                'group_label': group_label, 'event': event, 'sort_order': sort_order,
                'n_qualified': n, 'cutoff_seconds': float(cutoff), 'insufficient': False,
            })
        else:
            rows.append({
                'group_label': group_label, 'event': event, 'sort_order': sort_order,
                'n_qualified': n, 'cutoff_seconds': None, 'insufficient': True,
            })
    out = pd.DataFrame(rows).sort_values(['group_label', 'sort_order']).reset_index(drop=True)
    return out


def get_filter_options(results_df: pd.DataFrame) -> dict:
    """Distinct genders and group_names for the UI dropdowns."""
    if results_df.empty:
        return {'genders': [], 'groups': []}
    return {
        'genders': sorted(results_df['gender'].dropna().unique().tolist()),
        'groups': sorted(results_df['group_name'].dropna().unique().tolist()),
    }
