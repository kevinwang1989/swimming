"""Cross-competition progress leaderboard.

For each (participant, event) that has a timed result in two different
competitions, compute the time delta and expose ranked DataFrames for the UI.

Note on group matching: we intentionally do NOT require the same group_id
across competitions. Age-band groups (C/D/E/F) shift with the calendar year,
so a single athlete may appear in 女C in one season and 女B in the next —
it's still the same person, and their per-event progress is meaningful.
We expose both the earlier and later group labels so the UI can show the
transition (e.g. "女C → 女B").
"""

import pandas as pd
import streamlit as st

from db.connection import get_db


@st.cache_data(ttl=600)
def get_progress_data():
    """Return raw per-row progress DataFrame.

    Each row = one participant × one event with two timed results across
    two different competitions. Matching is by participant only (not group).
    """
    conn = get_db()
    sql = """
        SELECT
            p.id                 AS participant_id,
            p.name               AS name,
            p.district           AS district,
            g1.gender            AS earlier_gender,
            g1.group_name        AS earlier_group,
            g2.gender            AS later_gender,
            g2.group_name        AS later_group,
            ev.name              AS event_name,
            c1.name              AS earlier_comp,
            c1.date              AS earlier_date,
            r1.raw_value         AS earlier_raw,
            r1.numeric_value     AS earlier_seconds,
            c2.name              AS later_comp,
            c2.date              AS later_date,
            r2.raw_value         AS later_raw,
            r2.numeric_value     AS later_seconds
        FROM participant p
        JOIN enrollment e1 ON e1.participant_id = p.id
        JOIN enrollment e2 ON e2.participant_id = p.id
        JOIN competition c1 ON c1.id = e1.competition_id
        JOIN competition c2 ON c2.id = e2.competition_id
                          AND COALESCE(c2.date, '') > COALESCE(c1.date, '')
        JOIN group_def g1 ON g1.id = e1.group_id
        JOIN group_def g2 ON g2.id = e2.group_id
        JOIN result r1    ON r1.enrollment_id = e1.id
        JOIN result r2    ON r2.enrollment_id = e2.id
                          AND r2.event_id = r1.event_id
        JOIN event ev     ON ev.id = r1.event_id
        WHERE r1.status = 'normal' AND r2.status = 'normal'
          AND r1.numeric_value IS NOT NULL
          AND r2.numeric_value IS NOT NULL
          AND r1.numeric_value > 0
          AND r2.numeric_value > 0
          AND ev.category = 'swimming'
          AND ev.result_type = 'time'
    """
    df = pd.read_sql_query(sql, conn)
    conn.close()

    if df.empty:
        return df

    df['delta_seconds'] = df['later_seconds'] - df['earlier_seconds']
    df['delta_pct'] = 100.0 * df['delta_seconds'] / df['earlier_seconds']

    # Convenience fields for the UI
    df['gender'] = df['earlier_gender']  # filter key — gender rarely changes
    df['group_label'] = df.apply(
        lambda r: (
            f"{r['earlier_gender']}{r['earlier_group']}"
            if (r['earlier_gender'] == r['later_gender']
                and r['earlier_group'] == r['later_group'])
            else f"{r['earlier_gender']}{r['earlier_group']} → "
                 f"{r['later_gender']}{r['later_group']}"
        ),
        axis=1,
    )
    return df


def filter_progress(
    df: pd.DataFrame,
    gender: str = None,
    group_name: str = None,
    event_name: str = None,
    district: str = None,
) -> pd.DataFrame:
    """Apply UI filters to the raw progress dataframe.

    `group_name` matches the EARLIER group (i.e. where the athlete started).
    """
    if df.empty:
        return df
    out = df
    if gender:
        out = out[out['gender'] == gender]
    if group_name:
        out = out[out['earlier_group'] == group_name]
    if event_name:
        out = out[out['event_name'] == event_name]
    if district:
        out = out[out['district'] == district]
    return out


def summary_stats(df: pd.DataFrame) -> dict:
    """Return improvement / regression counts and average delta."""
    if df.empty:
        return {'improved': 0, 'regressed': 0, 'avg_delta': 0.0, 'total': 0}
    improved = int((df['delta_seconds'] < 0).sum())
    regressed = int((df['delta_seconds'] > 0).sum())
    avg_delta = float(df['delta_seconds'].mean())
    return {
        'improved': improved,
        'regressed': regressed,
        'avg_delta': avg_delta,
        'total': len(df),
    }


def top_improvers(df: pd.DataFrame, top_n: int = 20, by: str = 'seconds') -> pd.DataFrame:
    """Return the most-improved rows (most negative delta)."""
    if df.empty:
        return df
    sort_col = 'delta_seconds' if by == 'seconds' else 'delta_pct'
    return df.sort_values(sort_col, ascending=True).head(top_n).reset_index(drop=True)


def top_regressors(df: pd.DataFrame, top_n: int = 20, by: str = 'seconds') -> pd.DataFrame:
    """Return the most-regressed rows (most positive delta)."""
    if df.empty:
        return df
    sort_col = 'delta_seconds' if by == 'seconds' else 'delta_pct'
    return df.sort_values(sort_col, ascending=False).head(top_n).reset_index(drop=True)


def get_filter_options(df: pd.DataFrame) -> dict:
    """Distinct values for UI dropdowns, derived from the data we actually have."""
    if df.empty:
        return {'genders': [], 'groups': [], 'events': [], 'districts': []}
    return {
        'genders': sorted(df['gender'].dropna().unique().tolist()),
        'groups': sorted(df['earlier_group'].dropna().unique().tolist()),
        'events': sorted(df['event_name'].dropna().unique().tolist()),
        'districts': sorted(df['district'].dropna().unique().tolist()),
    }
