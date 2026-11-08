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

ALTER TABLE session_items
    DROP CONSTRAINT IF EXISTS session_items_question_id_fkey;

ALTER TABLE error_tags
    DROP CONSTRAINT IF EXISTS error_tags_question_id_fkey;

DO $$
DECLARE
    primary_key_columns TEXT;
BEGIN
    SELECT string_agg(a.attname, ',' ORDER BY a.attnum)
    INTO primary_key_columns
    FROM pg_constraint c
    JOIN pg_attribute a
      ON a.attrelid=c.conrelid
     AND a.attnum=ANY(c.conkey)
    WHERE c.conrelid='questions'::regclass
      AND c.contype='p';

    IF primary_key_columns = 'id' THEN
        ALTER TABLE questions DROP CONSTRAINT questions_pkey;
        ALTER TABLE questions
            ADD CONSTRAINT questions_pkey PRIMARY KEY (bank_id, id);
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname='error_tags_question_bank_fkey'
          AND conrelid='error_tags'::regclass
    ) THEN
        ALTER TABLE error_tags
            ADD CONSTRAINT error_tags_question_bank_fkey
            FOREIGN KEY (bank_id, question_id)
            REFERENCES questions (bank_id, id)
            ON DELETE RESTRICT;
    END IF;
END
$$;

COMMIT;
