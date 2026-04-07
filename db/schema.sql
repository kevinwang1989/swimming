PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS competition (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    short_name TEXT NOT NULL,
    date       TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS participant (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    district TEXT NOT NULL,
    UNIQUE(name, district)
);

CREATE TABLE IF NOT EXISTS group_def (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gender      TEXT NOT NULL CHECK(gender IN ('男', '女')),
    group_name  TEXT NOT NULL,
    format_type TEXT NOT NULL CHECK(format_type IN ('A', 'BtoE', 'F')),
    UNIQUE(gender, group_name)
);

CREATE TABLE IF NOT EXISTS event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL CHECK(category IN ('swimming', 'fitness')),
    result_type TEXT NOT NULL CHECK(result_type IN ('time', 'count', 'distance')),
    sort_order  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS enrollment (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL REFERENCES competition(id),
    participant_id INTEGER NOT NULL REFERENCES participant(id),
    group_id       INTEGER NOT NULL REFERENCES group_def(id),
    rank           INTEGER,
    total_score    REAL,
    rating         TEXT,
    remark         TEXT,
    UNIQUE(competition_id, participant_id, group_id)
);

CREATE TABLE IF NOT EXISTS result (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER NOT NULL REFERENCES enrollment(id),
    event_id      INTEGER NOT NULL REFERENCES event(id),
    raw_value     TEXT,
    numeric_value REAL,
    score         REAL,
    status        TEXT CHECK(status IN ('normal', 'foul', 'withdrew', 'missing'))
                  DEFAULT 'normal',
    UNIQUE(enrollment_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_enrollment_competition ON enrollment(competition_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_participant ON enrollment(participant_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_group ON enrollment(group_id);
CREATE INDEX IF NOT EXISTS idx_result_event ON result(event_id);
CREATE INDEX IF NOT EXISTS idx_result_enrollment ON result(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_participant_district ON participant(district);
CREATE INDEX IF NOT EXISTS idx_participant_name ON participant(name);
