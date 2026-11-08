BEGIN;

CREATE TABLE IF NOT EXISTS question_attempts (
    id BIGSERIAL PRIMARY KEY,
    student_id UUID NOT NULL,
    session_id UUID NOT NULL,
    bank_id UUID NOT NULL,
    question_id VARCHAR(100) NOT NULL,
    passage_id VARCHAR(100),
    question_type VARCHAR(20) NOT NULL
        CHECK (question_type IN ('cloze', 'grammar', 'reading', 'seven')),
    chosen_option TEXT,
    correct_option TEXT,
    is_correct BOOLEAN NOT NULL,
    attempt_kind VARCHAR(20) NOT NULL DEFAULT 'practice'
        CHECK (attempt_kind IN ('practice', 'review')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS question_attempts_student_question_idx
    ON question_attempts (student_id, question_id);
CREATE INDEX IF NOT EXISTS question_attempts_session_idx
    ON question_attempts (session_id);

CREATE TABLE IF NOT EXISTS mistake_items (
    student_id UUID NOT NULL,
    bank_id UUID NOT NULL,
    question_id VARCHAR(100) NOT NULL,
    passage_id VARCHAR(100),
    question_type VARCHAR(20) NOT NULL
        CHECK (question_type IN ('cloze', 'grammar', 'reading', 'seven')),
    first_wrong_at TIMESTAMPTZ NOT NULL,
    last_wrong_at TIMESTAMPTZ NOT NULL,
    wrong_count INTEGER NOT NULL DEFAULT 1 CHECK (wrong_count >= 1),
    correct_streak INTEGER NOT NULL DEFAULT 0
        CHECK (correct_streak BETWEEN 0 AND 2),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'mastered')),
    mastered_at TIMESTAMPTZ,
    last_review_at TIMESTAMPTZ,
    PRIMARY KEY (student_id, bank_id, question_id)
);

CREATE INDEX IF NOT EXISTS mistake_items_student_status_idx
    ON mistake_items (student_id, status);

CREATE TABLE IF NOT EXISTS report_deletions (
    session_id UUID PRIMARY KEY,
    student_id UUID NOT NULL,
    deleted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bank_switch_log (
    id BIGSERIAL PRIMARY KEY,
    from_bank_id UUID,
    to_bank_id UUID NOT NULL,
    switched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    operator TEXT
);

ALTER TABLE practice_sessions
    ADD COLUMN IF NOT EXISTS session_kind VARCHAR(20)
    NOT NULL DEFAULT 'practice';

ALTER TABLE practice_sessions
    DROP CONSTRAINT IF EXISTS practice_sessions_session_kind_check;

ALTER TABLE practice_sessions
    ADD CONSTRAINT practice_sessions_session_kind_check
    CHECK (session_kind IN ('practice', 'review'));

COMMIT;
