"""Import parsed PDF data into the SQLite database."""

import json

from db.connection import get_db
from importer.pdf_parser import parse_pdf
from importer.pdf_parser_final import parse_final_pdf, parse_time_to_seconds
from importer.value_parser import parse_result


def get_event_result_type(event_name):
    """Determine the result_type for an event based on its name."""
    if event_name in ('引体向上', '30秒仰卧起坐', '30秒双飞跳绳'):
        return 'count'
    elif event_name in ('立定跳远', '反臂体前屈'):
        return 'distance'
    else:
        return 'time'


def import_pdf(pdf_path, competition_name, short_name, date=None):
    """Import a competition PDF into the database.

    Args:
        pdf_path: Path to the PDF file
        competition_name: Full name (e.g. '2026游泳第一站')
        short_name: Short name (e.g. '第一站')
        date: Optional date string

    Returns:
        dict with import statistics
    """
    groups = parse_pdf(pdf_path)

    conn = get_db()
    stats = {'groups': 0, 'participants': 0, 'results': 0}

    try:
        # Create competition
        cur = conn.execute(
            "INSERT INTO competition (name, short_name, date) VALUES (?, ?, ?)",
            (competition_name, short_name, date)
        )
        competition_id = cur.lastrowid

        for group_data in groups:
            gender = group_data['gender']
            group_name = group_data['group_name']

            # Get group_def id
            row = conn.execute(
                "SELECT id FROM group_def WHERE gender=? AND group_name=?",
                (gender, group_name)
            ).fetchone()
            if not row:
                print(f"Warning: group {gender}{group_name} not found in group_def")
                continue
            group_id = row['id']
            stats['groups'] += 1

            for record in group_data['records']:
                # Upsert participant
                conn.execute(
                    "INSERT OR IGNORE INTO participant (name, district) VALUES (?, ?)",
                    (record['name'], record['district'])
                )
                participant = conn.execute(
                    "SELECT id FROM participant WHERE name=? AND district=?",
                    (record['name'], record['district'])
                ).fetchone()
                participant_id = participant['id']

                # Create enrollment
                cur = conn.execute(
                    """INSERT INTO enrollment
                       (competition_id, participant_id, group_id, rank, total_score, rating, remark)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (competition_id, participant_id, group_id,
                     record['rank'], record['total_score'],
                     record.get('rating'), record.get('remark'))
                )
                enrollment_id = cur.lastrowid
                stats['participants'] += 1

                # Insert results
                for res in record['results']:
                    event_name = res['event']

                    # Get or create event
                    evt = conn.execute(
                        "SELECT id, result_type FROM event WHERE name=?",
                        (event_name,)
                    ).fetchone()
                    if not evt:
                        # Auto-create event if not predefined
                        result_type = get_event_result_type(event_name)
                        conn.execute(
                            "INSERT INTO event (name, category, result_type, sort_order) VALUES (?, ?, ?, ?)",
                            (event_name,
                             'fitness' if result_type != 'time' else 'swimming',
                             result_type, 99)
                        )
                        evt = conn.execute(
                            "SELECT id, result_type FROM event WHERE name=?",
                            (event_name,)
                        ).fetchone()

                    event_id = evt['id']
                    result_type = evt['result_type']

                    # Parse the value
                    numeric_value, status = parse_result(res['raw_value'], result_type)

                    conn.execute(
                        """INSERT OR IGNORE INTO result
                           (enrollment_id, event_id, raw_value, numeric_value, score, status)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (enrollment_id, event_id, res['raw_value'],
                         numeric_value, res.get('score'), status)
                    )
                    stats['results'] += 1

        conn.commit()
        print(f"Import complete: {stats}")
        return stats

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def _get_or_create_event(conn, event_name, is_relay=False):
    evt = conn.execute("SELECT id FROM event WHERE name=?", (event_name,)).fetchone()
    if evt:
        return evt['id']
    category = 'swimming'
    result_type = 'time'
    cur = conn.execute(
        "INSERT INTO event (name, category, result_type, sort_order) VALUES (?, ?, ?, ?)",
        (event_name, category, result_type, 50 if is_relay else 25)
    )
    return cur.lastrowid


def import_final_pdf(pdf_path, competition_name, short_name, date=None):
    """Import a 2025-finals-format PDF (per-event tables, with segments + relays)."""
    parsed = parse_final_pdf(pdf_path)
    events = parsed['events']
    relays = parsed['relays']

    conn = get_db()
    stats = {'events': 0, 'records': 0, 'relay_teams': 0, 'relay_legs': 0}

    try:
        cur = conn.execute(
            "INSERT INTO competition (name, short_name, date) VALUES (?, ?, ?)",
            (competition_name, short_name, date)
        )
        competition_id = cur.lastrowid

        # ---- Individual events ----
        for (gender, group_name, event_name), records in events.items():
            row = conn.execute(
                "SELECT id FROM group_def WHERE gender=? AND group_name=?",
                (gender, group_name)
            ).fetchone()
            if not row:
                print(f"Warning: group {gender}{group_name} not found")
                continue
            group_id = row['id']
            event_id = _get_or_create_event(conn, event_name)
            stats['events'] += 1

            for rec in records:
                # Upsert participant
                conn.execute(
                    "INSERT OR IGNORE INTO participant (name, district) VALUES (?, ?)",
                    (rec['name'], rec['district'])
                )
                participant_id = conn.execute(
                    "SELECT id FROM participant WHERE name=? AND district=?",
                    (rec['name'], rec['district'])
                ).fetchone()['id']

                # Enrollment (one per (competition, participant, group); shared across events)
                enrollment = conn.execute(
                    "SELECT id FROM enrollment WHERE competition_id=? AND participant_id=? AND group_id=?",
                    (competition_id, participant_id, group_id)
                ).fetchone()
                if enrollment:
                    enrollment_id = enrollment['id']
                else:
                    enrollment_id = conn.execute(
                        """INSERT INTO enrollment
                           (competition_id, participant_id, group_id, rank, total_score, rating, remark)
                           VALUES (?, ?, ?, NULL, NULL, NULL, NULL)""",
                        (competition_id, participant_id, group_id)
                    ).lastrowid

                raw_value = rec.get('final_time')
                numeric_value = parse_time_to_seconds(raw_value) if raw_value else None
                splits_json = json.dumps(rec.get('splits') or [], ensure_ascii=False)

                conn.execute(
                    """INSERT OR IGNORE INTO result
                       (enrollment_id, event_id, raw_value, numeric_value, score, status,
                        splits, reaction_time, athlete_level)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (enrollment_id, event_id, raw_value, numeric_value,
                     rec.get('score'), rec.get('status', 'normal'),
                     splits_json, rec.get('rt'), rec.get('level'))
                )
                stats['records'] += 1

        # ---- Relay events ----
        for (gender, group_name, event_name), teams in relays.items():
            row = conn.execute(
                "SELECT id FROM group_def WHERE gender=? AND group_name=?",
                (gender, group_name)
            ).fetchone()
            if not row:
                continue
            group_id = row['id']
            event_id = _get_or_create_event(conn, event_name, is_relay=True)

            for team in teams:
                team_cur = conn.execute(
                    """INSERT INTO relay_team
                       (competition_id, group_id, event_id, rank, heat, lane, district,
                        final_time, final_seconds, total_score, athlete_level, status, remark)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (competition_id, group_id, event_id,
                     team.get('rank'), team.get('heat'), team.get('lane'),
                     team['district'], team.get('final_time'), team.get('final_seconds'),
                     team.get('total_score'), team.get('athlete_level'),
                     team.get('status', 'normal'), team.get('remark'))
                )
                team_id = team_cur.lastrowid
                stats['relay_teams'] += 1

                for leg in team['legs']:
                    leg_splits = []
                    prev = 0.0
                    for i, t in enumerate(leg.get('splits') or []):
                        cum_s = parse_time_to_seconds(t)
                        leg_splits.append({
                            'dist': (i + 1) * 50,
                            'cum': cum_s,
                            'lap': (cum_s - prev) if cum_s is not None else None,
                        })
                        if cum_s is not None:
                            prev = cum_s
                    conn.execute(
                        """INSERT INTO relay_leg
                           (relay_team_id, leg_order, swimmer_name, reaction_time, splits,
                            leg_time, leg_seconds, cumulative_time, cumulative_seconds)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (team_id, leg['order'], leg['name'], leg.get('rt'),
                         json.dumps(leg_splits, ensure_ascii=False),
                         leg.get('leg_time'), leg.get('leg_seconds'),
                         leg.get('cum'), leg.get('cum_seconds'))
                    )
                    stats['relay_legs'] += 1

        conn.commit()
        print(f"Final import complete: {stats}")
        return stats
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
