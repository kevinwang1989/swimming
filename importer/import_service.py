"""Import parsed PDF data into the SQLite database."""

from db.connection import get_db
from importer.pdf_parser import parse_pdf
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
