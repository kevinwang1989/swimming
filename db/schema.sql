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
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id  INTEGER NOT NULL REFERENCES enrollment(id),
    event_id       INTEGER NOT NULL REFERENCES event(id),
    raw_value      TEXT,
    numeric_value  REAL,
    score          REAL,
    status         TEXT CHECK(status IN ('normal', 'foul', 'withdrew', 'missing'))
                   DEFAULT 'normal',
    splits         TEXT,  -- JSON: [{"dist":50,"cum":24.33,"lap":24.33,"stroke":null}, ...]
    reaction_time  REAL,  -- R.T. 反应时间 (seconds)
    athlete_level  TEXT,  -- 运动等级: 一级/二级/三级/无等级
    UNIQUE(enrollment_id, event_id)
);

CREATE TABLE IF NOT EXISTS relay_team (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id  INTEGER NOT NULL REFERENCES competition(id),
    group_id        INTEGER NOT NULL REFERENCES group_def(id),
    event_id        INTEGER NOT NULL REFERENCES event(id),
    rank            INTEGER,
    heat            INTEGER,
    lane            INTEGER,
    district        TEXT NOT NULL,
    final_time      TEXT,
    final_seconds   REAL,
    total_score     REAL,
    athlete_level   TEXT,
    status          TEXT CHECK(status IN ('normal', 'foul', 'withdrew', 'missing'))
                    DEFAULT 'normal',
    remark          TEXT,
    UNIQUE(competition_id, group_id, event_id, district)
);

CREATE TABLE IF NOT EXISTS relay_leg (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    relay_team_id     INTEGER NOT NULL REFERENCES relay_team(id),
    leg_order         INTEGER NOT NULL,
    swimmer_name      TEXT NOT NULL,
    reaction_time     REAL,
    splits            TEXT,  -- JSON: per-50m splits within this leg
    leg_time          TEXT,
    leg_seconds       REAL,
    cumulative_time   TEXT,
    cumulative_seconds REAL,
    UNIQUE(relay_team_id, leg_order)
);

CREATE INDEX IF NOT EXISTS idx_relay_team_event ON relay_team(competition_id, event_id);
CREATE INDEX IF NOT EXISTS idx_relay_leg_team ON relay_leg(relay_team_id);

CREATE INDEX IF NOT EXISTS idx_enrollment_competition ON enrollment(competition_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_participant ON enrollment(participant_id);
CREATE INDEX IF NOT EXISTS idx_enrollment_group ON enrollment(group_id);
CREATE INDEX IF NOT EXISTS idx_result_event ON result(event_id);
CREATE INDEX IF NOT EXISTS idx_result_enrollment ON result(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_participant_district ON participant(district);
CREATE INDEX IF NOT EXISTS idx_participant_name ON participant(name);

-- ── Auth & Analytics (v1.8) ─────────────────────────────────

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
