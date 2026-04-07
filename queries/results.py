"""Query functions for browsing competition results."""

import pandas as pd
from db.connection import get_db


def get_competitions():
    """Return all competitions."""
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM competition ORDER BY date DESC, id DESC", conn)
    conn.close()
    return df


def get_groups():
    """Return all group definitions."""
    conn = get_db()
    df = pd.read_sql_query(
        "SELECT * FROM group_def ORDER BY gender, group_name", conn
    )
    conn.close()
    return df


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

    # Pivot results into columns
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


def get_all_districts():
    """Return all distinct districts."""
    conn = get_db()
    districts = [r[0] for r in conn.execute(
        "SELECT DISTINCT district FROM participant ORDER BY district"
    ).fetchall()]
    conn.close()
    return districts
