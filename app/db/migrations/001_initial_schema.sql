-- Run once in the Supabase SQL editor

CREATE TABLE participants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone           TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    is_main_admin   BOOLEAN NOT NULL DEFAULT FALSE,
    joined_at       DATE NOT NULL DEFAULT '2026-01-01',
    medical_leave_days INT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    resigned_at     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE workouts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id   UUID NOT NULL REFERENCES participants(id),
    workout_date     DATE NOT NULL,
    submitted_at     TIMESTAMPTZ NOT NULL,
    sequence_number  INT NOT NULL,
    shift            TEXT NOT NULL CHECK (shift IN ('madrugada','manha','tarde','noite')),
    modality         TEXT,
    photo_url        TEXT,
    photo_message_id TEXT,
    text_message_id  TEXT,
    is_valid         BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at       TIMESTAMPTZ,
    deleted_by       UUID REFERENCES participants(id),
    deletion_reason  TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(participant_id, workout_date, shift)
);

CREATE INDEX idx_workouts_participant_date ON workouts(participant_id, workout_date);
CREATE INDEX idx_workouts_submitted_at    ON workouts(submitted_at);

CREATE TABLE pending_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id  UUID NOT NULL REFERENCES participants(id),
    message_id      TEXT NOT NULL UNIQUE,
    message_type    TEXT NOT NULL CHECK (message_type IN ('photo', 'text')),
    raw_payload     JSONB NOT NULL,
    photo_url       TEXT,
    sequence_number INT,
    raw_text        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '3 hours')
);

CREATE INDEX idx_pending_participant ON pending_messages(participant_id, created_at);

CREATE TABLE reports (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    trigger      TEXT NOT NULL CHECK (trigger IN ('scheduled', 'manual')),
    triggered_by UUID REFERENCES participants(id),
    period_start DATE NOT NULL,
    period_end   DATE NOT NULL,
    snapshot     JSONB NOT NULL,
    report_text  TEXT NOT NULL,
    sent_at      TIMESTAMPTZ
);

CREATE TABLE disputes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_id      UUID NOT NULL REFERENCES workouts(id),
    raised_by       UUID NOT NULL REFERENCES participants(id),
    raised_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved_deletion', 'rejected', 'escalated')),
    resolved_by     UUID REFERENCES participants(id),
    resolved_at     TIMESTAMPTZ,
    resolution_note TEXT
);

-- Storage bucket: create manually in Supabase Dashboard
-- Bucket name: workout-photos  (public read, authenticated write)
-- Path pattern: {phone}/{workout_date}/{message_id}.jpg
