"""Query functions for comparison and cross-competition analysis."""

import pandas as pd
import streamlit as st
from db.connection import get_db


@st.cache_data(ttl=600)
def compare_participants(participant_ids, competition_id=None):
    """Side-by-side comparison of multiple participants.

    Returns a DataFrame with events as rows, participant results as columns.
    """
    conn = get_db()
    # Convert to tuple for cache hashability
    if not isinstance(participant_ids, tuple):
        participant_ids = tuple(participant_ids)
    placeholders = ','.join(['?'] * len(participant_ids))

    comp_filter = ""
    params = list(participant_ids)
    if competition_id:
        comp_filter = "AND e.competition_id = ?"
        params.append(competition_id)

    df = pd.read_sql_query(f"""
        SELECT p.id as participant_id, p.name, p.district,
               c.short_name as competition,
               g.gender, g.group_name,
               ev.name as event_name, ev.sort_order, ev.result_type,
               r.raw_value, r.numeric_value, r.score, r.status
        FROM enrollment e
        JOIN participant p ON p.id = e.participant_id
        JOIN competition c ON c.id = e.competition_id
        JOIN group_def g ON g.id = e.group_id
        JOIN result r ON r.enrollment_id = e.id
        JOIN event ev ON ev.id = r.event_id
        WHERE p.id IN ({placeholders})
        {comp_filter}
        ORDER BY ev.sort_order
    """, conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=600)
def participant_progression(participant_id):
    """Track a participant's results across all competitions.

    Returns a DataFrame sorted by competition date and event.
    """
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT c.id as competition_id, c.name as competition,
               c.short_name, c.date,
               g.gender, g.group_name,
               e.rank, e.total_score,
               ev.name as event_name, ev.sort_order, ev.result_type,
               r.raw_value, r.numeric_value, r.score, r.status
        FROM enrollment e
        JOIN competition c ON c.id = e.competition_id
        JOIN group_def g ON g.id = e.group_id
        JOIN result r ON r.enrollment_id = e.id
        JOIN event ev ON ev.id = r.event_id
        WHERE e.participant_id = ?
        ORDER BY c.date, c.id, ev.sort_order
    """, conn, params=(participant_id,))
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_event_ranking(competition_id, event_name, gender=None, group_name=None, limit=50):
    """Get ranking for a specific event in a competition."""
    conn = get_db()

    filters = ["e.competition_id = ?", "ev.name = ?"]
    params = [competition_id, event_name]

    if gender:
        filters.append("g.gender = ?")
        params.append(gender)
    if group_name:
        filters.append("g.group_name = ?")
        params.append(group_name)

    where = " AND ".join(filters)
    params.append(limit)

    df = pd.read_sql_query(f"""
        SELECT p.name, p.district, g.gender, g.group_name,
               r.raw_value, r.numeric_value, r.score, r.status
        FROM result r
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN participant p ON p.id = e.participant_id
        JOIN group_def g ON g.id = e.group_id
        JOIN event ev ON ev.id = r.event_id
        WHERE {where}
          AND r.status = 'normal'
        ORDER BY r.numeric_value ASC
        LIMIT ?
    """, conn, params=params)
    conn.close()
    return df
