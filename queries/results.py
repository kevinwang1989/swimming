"""Query functions for browsing competition results."""

import json

import pandas as pd
import streamlit as st
from db.connection import get_db


@st.cache_data(ttl=600)
def get_competitions():
    """Return all competitions."""
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM competition ORDER BY date DESC, id DESC", conn)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_groups():
    """Return all group definitions."""
    conn = get_db()
    df = pd.read_sql_query(
        "SELECT * FROM group_def ORDER BY gender, group_name", conn
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_group_results(competition_id, gender, group_name):
    """Get full results table for a group in a competition.

    Returns a DataFrame with one row per participant, columns for each event.
    """
    conn = get_db()

    # Get base enrollment info
    enrollments = pd.read_sql_query("""
        SELECT e.id as enrollment_id, e.rank, p.name, p.district,
               e.total_score, e.rating, e.remark
        FROM enrollment e
        JOIN participant p ON p.id = e.participant_id
        JOIN group_def g ON g.id = e.group_id
        WHERE e.competition_id = ?
          AND g.gender = ? AND g.group_name = ?
        ORDER BY e.rank
    """, conn, params=(competition_id, gender, group_name))

    if enrollments.empty:
        conn.close()
        return enrollments

    enrollment_ids = enrollments['enrollment_id'].tolist()

    # Get all results for these enrollments
    placeholders = ','.join(['?'] * len(enrollment_ids))
    results = pd.read_sql_query(f"""
        SELECT r.enrollment_id, ev.name as event_name,
               r.raw_value, r.score, r.status
        FROM result r
        JOIN event ev ON ev.id = r.event_id
        WHERE r.enrollment_id IN ({placeholders})
        ORDER BY ev.sort_order
    """, conn, params=enrollment_ids)

    conn.close()

    if results.empty:
        return enrollments

    # Pivot results into columns using vectorized approach
    for _, row in results.iterrows():
        eid = row['enrollment_id']
        event = row['event_name']
        mask = enrollments['enrollment_id'] == eid

        display_val = row['raw_value'] or ''
        if row['status'] == 'foul':
            display_val = '犯规'
        elif row['status'] == 'withdrew':
            display_val = '弃权'

        enrollments.loc[mask, f'{event}_成绩'] = display_val
        enrollments.loc[mask, f'{event}_得分'] = row['score']

    enrollments.drop(columns=['enrollment_id'], inplace=True)
    return enrollments


@st.cache_data(ttl=600)
def get_events_for_group(competition_id, gender, group_name):
    """Get the list of events that have results for a given group."""
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT DISTINCT ev.name, ev.sort_order, ev.category, ev.result_type
        FROM result r
        JOIN event ev ON ev.id = r.event_id
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN group_def g ON g.id = e.group_id
        WHERE e.competition_id = ?
          AND g.gender = ? AND g.group_name = ?
        ORDER BY ev.sort_order
    """, conn, params=(competition_id, gender, group_name))
    conn.close()
    return df


@st.cache_data(ttl=600)
def search_participants(name_query='', district=None):
    """Search participants by name (fuzzy) and optional district."""
    conn = get_db()
    query = "SELECT * FROM participant WHERE 1=1"
    params = []

    if name_query:
        query += " AND name LIKE ?"
        params.append(f'%{name_query}%')
    if district:
        query += " AND district = ?"
        params.append(district)

    query += " ORDER BY name LIMIT 200"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_participant_history(participant_id):
    """Get all competition results for a participant across all competitions."""
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT c.name as competition, c.short_name, c.date,
               g.gender, g.group_name,
               e.rank, e.total_score, e.rating, e.remark,
               ev.name as event_name, ev.category, ev.result_type,
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
def get_group_total_count(competition_name, gender, group_name):
    """Get total number of participants in a group for a competition."""
    conn = get_db()
    row = conn.execute("""
        SELECT COUNT(*) FROM enrollment e
        JOIN competition c ON c.id = e.competition_id
        JOIN group_def g ON g.id = e.group_id
        WHERE c.name = ? AND g.gender = ? AND g.group_name = ?
    """, (competition_name, gender, group_name)).fetchone()
    conn.close()
    return row[0] if row else 0


@st.cache_data(ttl=600)
def get_events_for_competition(competition_id, gender=None, group_name=None, include_relay=True):
    """List events that have data (individual or relay) in this competition.

    Returns DataFrame with columns: name, sort_order, kind ('individual' or 'relay'),
    gender, group_name.
    """
    conn = get_db()
    rows = []

    # Individual events (from result + enrollment)
    q1 = """
        SELECT DISTINCT ev.name, ev.sort_order, g.gender, g.group_name
        FROM result r
        JOIN event ev ON ev.id = r.event_id
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN group_def g ON g.id = e.group_id
        WHERE e.competition_id = ?
    """
    p1 = [competition_id]
    if gender:
        q1 += " AND g.gender = ?"
        p1.append(gender)
    if group_name:
        q1 += " AND g.group_name = ?"
        p1.append(group_name)
    df1 = pd.read_sql_query(q1, conn, params=p1)
    df1['kind'] = 'individual'
    rows.append(df1)

    if include_relay:
        q2 = """
            SELECT DISTINCT ev.name, ev.sort_order, g.gender, g.group_name
            FROM relay_team rt
            JOIN event ev ON ev.id = rt.event_id
            JOIN group_def g ON g.id = rt.group_id
            WHERE rt.competition_id = ?
        """
        p2 = [competition_id]
        if gender:
            q2 += " AND g.gender = ?"
            p2.append(gender)
        if group_name:
            q2 += " AND g.group_name = ?"
            p2.append(group_name)
        df2 = pd.read_sql_query(q2, conn, params=p2)
        df2['kind'] = 'relay'
        rows.append(df2)

    conn.close()
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if not out.empty:
        out = out.sort_values(['sort_order', 'name']).reset_index(drop=True)
    return out


@st.cache_data(ttl=600)
def get_event_results(competition_id, gender, group_name, event_name):
    """Get individual results for one event in one group.

    Returns DataFrame with rows ordered by rank/time, including a parsed `splits` list.
    """
    conn = get_db()
    df = pd.read_sql_query("""
        SELECT p.name, p.district,
               r.raw_value, r.numeric_value, r.score, r.status,
               r.splits, r.reaction_time, r.athlete_level
        FROM result r
        JOIN enrollment e ON e.id = r.enrollment_id
        JOIN participant p ON p.id = e.participant_id
        JOIN group_def g ON g.id = e.group_id
        JOIN event ev ON ev.id = r.event_id
        WHERE e.competition_id = ?
          AND g.gender = ? AND g.group_name = ?
          AND ev.name = ?
        ORDER BY
            CASE WHEN r.status='normal' THEN 0 ELSE 1 END,
            r.numeric_value
    """, conn, params=(competition_id, gender, group_name, event_name))
    conn.close()

    if df.empty:
        return df

    def _parse(s):
        if not s:
            return []
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return []

    df['splits'] = df['splits'].apply(_parse)
    df.insert(0, 'rank', range(1, len(df) + 1))
    # Reset rank for non-normal status to None
    df.loc[df['status'] != 'normal', 'rank'] = None
    return df


@st.cache_data(ttl=600)
def get_relay_results(competition_id, gender, group_name, event_name):
    """Get relay teams + their legs for one relay event in one group.

    Returns (teams_df, legs_df). teams_df has one row per team; legs_df has team_id link.
    """
    conn = get_db()
    teams = pd.read_sql_query("""
        SELECT rt.id as team_id, rt.rank, rt.heat, rt.lane, rt.district,
               rt.final_time, rt.final_seconds, rt.total_score,
               rt.athlete_level, rt.status, rt.remark
        FROM relay_team rt
        JOIN group_def g ON g.id = rt.group_id
        JOIN event ev ON ev.id = rt.event_id
        WHERE rt.competition_id = ?
          AND g.gender = ? AND g.group_name = ?
          AND ev.name = ?
        ORDER BY
            CASE WHEN rt.status='normal' THEN 0 ELSE 1 END,
            rt.final_seconds
    """, conn, params=(competition_id, gender, group_name, event_name))

    if teams.empty:
        conn.close()
        return teams, pd.DataFrame()

    placeholders = ','.join(['?'] * len(teams))
    legs = pd.read_sql_query(f"""
        SELECT rl.relay_team_id as team_id, rl.leg_order, rl.swimmer_name,
               rl.reaction_time, rl.splits, rl.leg_time, rl.leg_seconds,
               rl.cumulative_time, rl.cumulative_seconds
        FROM relay_leg rl
        WHERE rl.relay_team_id IN ({placeholders})
        ORDER BY rl.relay_team_id, rl.leg_order
    """, conn, params=teams['team_id'].tolist())
    conn.close()
    return teams, legs


@st.cache_data(ttl=600)
def get_all_districts():
    """Return all distinct districts."""
    conn = get_db()
    districts = [r[0] for r in conn.execute(
        "SELECT DISTINCT district FROM participant ORDER BY district"
    ).fetchall()]
    conn.close()
    return districts


@st.cache_data(ttl=600)
def get_site_stats():
    """Return homepage-level counts: competitions, participants, results, districts."""
    conn = get_db()
    cur = conn.cursor()
    stats = {
        'competitions': cur.execute("SELECT COUNT(*) FROM competition").fetchone()[0],
        'participants': cur.execute("SELECT COUNT(*) FROM participant").fetchone()[0],
        'results': cur.execute("SELECT COUNT(*) FROM result").fetchone()[0],
        'districts': cur.execute(
            "SELECT COUNT(DISTINCT district) FROM participant"
        ).fetchone()[0],
    }
    conn.close()
    return stats
