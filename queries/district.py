"""Query functions for district-level analysis."""

import pandas as pd
import streamlit as st
from db.connection import get_db


@st.cache_data(ttl=600)
def district_summary(competition_id, gender=None, group_name=None):
    """Aggregate statistics per district.

    Returns DataFrame with columns:
    district, participant_count, avg_score, total_score, promoted_count, excellent_count
    """
    conn = get_db()

    filters = ["e.competition_id = ?"]
    params = [competition_id]

    if gender:
        filters.append("g.gender = ?")
        params.append(gender)
    if group_name:
        filters.append("g.group_name = ?")
        params.append(group_name)

    where = " AND ".join(filters)

    df = pd.read_sql_query(f"""
        SELECT p.district,
               COUNT(DISTINCT p.id) as participant_count,
               ROUND(AVG(e.total_score), 2) as avg_score,
               ROUND(SUM(e.total_score), 2) as total_score,
               SUM(CASE WHEN e.remark LIKE '%晋级%' THEN 1 ELSE 0 END) as promoted_count,
               SUM(CASE WHEN e.rating = '优秀' THEN 1 ELSE 0 END) as excellent_count
        FROM enrollment e
        JOIN participant p ON p.id = e.participant_id
        JOIN group_def g ON g.id = e.group_id
        WHERE {where}
        GROUP BY p.district
        ORDER BY avg_score DESC
    """, conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=600)
def district_event_comparison(competition_id, event_name, gender=None):
    """Compare districts on a specific event.

    Returns DataFrame with district-level average performance.
    """
    conn = get_db()

    filters = ["e.competition_id = ?", "ev.name = ?", "r.status = 'normal'"]
    params = [competition_id, event_name]

    if gender:
        filters.append("g.gender = ?")
        params.append(gender)

    where = " AND ".join(filters)

    df = pd.read_sql_query(f"""
        SELECT p.district,
               COUNT(*) as athlete_count,
               ROUND(AVG(r.numeric_value), 2) as avg_result,
               ROUND(MIN(r.numeric_value), 2) as best_result,
               ROUND(AVG(r.score), 2) as avg_score
        FROM result r
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN participant p ON p.id = e.participant_id
        JOIN group_def g ON g.id = e.group_id
        JOIN event ev ON ev.id = r.event_id
        WHERE {where}
        GROUP BY p.district
        HAVING athlete_count >= 1
        ORDER BY avg_result ASC
    """, conn, params=params)
    conn.close()
    return df
