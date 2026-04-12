import os
import sqlite3
from db.connection import get_db, DB_PATH

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

# Pre-defined groups
GROUPS = [
    ('男', 'A', 'A'), ('女', 'A', 'A'),
    ('男', 'B', 'BtoE'), ('女', 'B', 'BtoE'),
    ('男', 'C', 'BtoE'), ('女', 'C', 'BtoE'),
    ('男', 'D', 'BtoE'), ('女', 'D', 'BtoE'),
    ('男', 'E', 'BtoE'), ('女', 'E', 'BtoE'),
    ('男', 'F', 'F'), ('女', 'F', 'F'),
]

# Pre-defined events: (name, category, result_type, sort_order)
EVENTS = [
    # Swimming - 100m (B-E groups)
    ('100米自由泳', 'swimming', 'time', 1),
    ('100米仰泳', 'swimming', 'time', 2),
    ('100米蛙泳', 'swimming', 'time', 3),
    ('100米蝶泳', 'swimming', 'time', 4),
    ('100米自由泳腿', 'swimming', 'time', 5),
    ('100米仰泳腿', 'swimming', 'time', 6),
    ('100米蛙泳腿', 'swimming', 'time', 7),
    ('100米蝶泳腿', 'swimming', 'time', 8),
    # Swimming - 50m (F group)
    ('50米自由泳', 'swimming', 'time', 11),
    ('50米仰泳', 'swimming', 'time', 12),
    ('50米蛙泳', 'swimming', 'time', 13),
    ('50米蝶泳', 'swimming', 'time', 14),
    ('50米自由泳腿', 'swimming', 'time', 15),
    ('50米仰泳腿', 'swimming', 'time', 16),
    ('50米蛙泳腿', 'swimming', 'time', 17),
    ('50米蝶泳腿', 'swimming', 'time', 18),
    # Swimming - longer distances
    ('200米混合泳', 'swimming', 'time', 21),
    ('200米个人混合泳', 'swimming', 'time', 22),
    ('400米自由泳', 'swimming', 'time', 23),
    # Fitness
    ('引体向上', 'fitness', 'count', 31),
    ('30秒仰卧起坐', 'fitness', 'count', 32),
    ('30秒双飞跳绳', 'fitness', 'count', 33),
    ('立定跳远', 'fitness', 'distance', 34),
    ('反臂体前屈', 'fitness', 'distance', 35),
]


def _migrate_result_columns(conn):
    """Idempotent migration: ensure result table has v1.1 columns."""
    cols = {r['name'] for r in conn.execute("PRAGMA table_info(result)")}
    if 'splits' not in cols:
        conn.execute("ALTER TABLE result ADD COLUMN splits TEXT")
    if 'reaction_time' not in cols:
        conn.execute("ALTER TABLE result ADD COLUMN reaction_time REAL")
    if 'athlete_level' not in cols:
        conn.execute("ALTER TABLE result ADD COLUMN athlete_level TEXT")


def _migrate_auth_tables(conn):
    """Idempotent migration: create auth & analytics tables (v1.8)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS app_user (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name  TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'viewer'
                          CHECK(role IN ('viewer', 'coach', 'admin')),
            invite_code   TEXT NOT NULL UNIQUE,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT DEFAULT (datetime('now')),
            last_login_at TEXT
        );

        CREATE TABLE IF NOT EXISTS user_session (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES app_user(id),
            token      TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analytics_event (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER REFERENCES app_user(id),
            event_type TEXT NOT NULL,
            page       TEXT,
            detail     TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_session_token ON user_session(token);
        CREATE INDEX IF NOT EXISTS idx_session_user ON user_session(user_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_user ON analytics_event(user_id);
        CREATE INDEX IF NOT EXISTS idx_analytics_time ON analytics_event(created_at);
        CREATE INDEX IF NOT EXISTS idx_analytics_page ON analytics_event(page);
    """)

    # Seed admin user
    admin_code = os.environ.get("ADMIN_CODE", "SWIM-ADMIN")
    conn.execute(
        "INSERT OR IGNORE INTO app_user (display_name, role, invite_code) VALUES (?, ?, ?)",
        ("Admin", "admin", admin_code.upper()),
    )


def init_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_db()
    try:
        with open(SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())

        _migrate_result_columns(conn)
        _migrate_auth_tables(conn)

        # Seed groups
        for gender, group_name, format_type in GROUPS:
            conn.execute(
                "INSERT OR IGNORE INTO group_def (gender, group_name, format_type) VALUES (?, ?, ?)",
                (gender, group_name, format_type)
            )

        # Seed events
        for name, category, result_type, sort_order in EVENTS:
            conn.execute(
                "INSERT OR IGNORE INTO event (name, category, result_type, sort_order) VALUES (?, ?, ?, ?)",
                (name, category, result_type, sort_order)
            )

        conn.commit()
        print(f"Database initialized at {DB_PATH}")
    finally:
        conn.close()


if __name__ == '__main__':
    init_database()
