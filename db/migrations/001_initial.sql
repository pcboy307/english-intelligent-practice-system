BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE question_banks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(80) NOT NULL,
    target_size INTEGER NOT NULL CHECK (target_size > 0),
    difficulty_profile VARCHAR(20) NOT NULL
        CHECK (difficulty_profile IN ('standard', 'foundation', 'advanced')),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'generating', 'reviewing', 'ready', 'active', 'archived')),
    coverage_snapshot JSONB,
    generation_job_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    CONSTRAINT question_banks_active_has_snapshot
        CHECK (status <> 'active' OR coverage_snapshot IS NOT NULL)
);

CREATE UNIQUE INDEX one_active_bank
    ON question_banks ((status))
    WHERE status = 'active';

CREATE INDEX question_banks_status_idx ON question_banks (status, created_at DESC);

CREATE TABLE generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL
        CHECK (status IN ('queued', 'running', 'paused_for_review', 'paused_for_owner', 'completed', 'failed')),
    batch_size INTEGER NOT NULL DEFAULT 10 CHECK (batch_size BETWEEN 1 AND 10),
    target_passages INTEGER NOT NULL CHECK (target_passages > 0),
    completed_passages INTEGER NOT NULL DEFAULT 0 CHECK (completed_passages >= 0),
    rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    first_batch_verified BOOLEAN NOT NULL DEFAULT FALSE,
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX one_running_generation_job_per_bank
    ON generation_jobs (bank_id)
    WHERE status IN ('queued', 'running', 'paused_for_review', 'paused_for_owner');

ALTER TABLE question_banks
    ADD CONSTRAINT question_banks_generation_job_fk
    FOREIGN KEY (generation_job_id) REFERENCES generation_jobs(id) ON DELETE SET NULL;

CREATE TABLE generation_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES generation_jobs(id) ON DELETE RESTRICT,
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    batch_number INTEGER NOT NULL CHECK (batch_number > 0),
    passage_target INTEGER NOT NULL CHECK (passage_target BETWEEN 1 AND 10),
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('queued', 'running', 'validated', 'paused', 'failed')),
    accepted_count INTEGER NOT NULL DEFAULT 0 CHECK (accepted_count >= 0),
    rejected_count INTEGER NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    UNIQUE (job_id, batch_number)
);

CREATE TABLE passages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    passage_group_id VARCHAR(100) NOT NULL,
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    type VARCHAR(20) NOT NULL
        CHECK (type IN ('cloze', 'grammar_fill', 'reading', 'gap_fill')),
    content TEXT NOT NULL,
    word_count INTEGER NOT NULL CHECK (word_count > 0),
    topic VARCHAR(100) NOT NULL,
    book_source VARCHAR(100) NOT NULL,
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'reviewed', 'published', 'archived')),
    out_of_scope_flags TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (bank_id, passage_group_id),
    UNIQUE (bank_id, id),
    CONSTRAINT passage_word_limit CHECK (
        word_count <= CASE type
            WHEN 'cloze' THEN 220
            WHEN 'grammar_fill' THEN 180
            WHEN 'reading' THEN 250
            WHEN 'gap_fill' THEN 220
        END
    )
);

CREATE INDEX passages_bank_type_status_idx ON passages (bank_id, type, status);

CREATE TABLE questions (
    id VARCHAR(100) PRIMARY KEY,
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    type VARCHAR(20) NOT NULL
        CHECK (type IN ('cloze', 'grammar_fill', 'reading', 'gap_fill')),
    passage_group_id VARCHAR(100) NOT NULL,
    stem TEXT NOT NULL,
    options JSONB,
    answer JSONB NOT NULL,
    explanation TEXT NOT NULL,
    knowledge_points TEXT[] NOT NULL CHECK (cardinality(knowledge_points) > 0),
    grammar_tags TEXT[] NOT NULL DEFAULT '{}',
    book_source VARCHAR(100) NOT NULL,
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    out_of_scope_flags TEXT[] NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'reviewed', 'published', 'archived')),
    batch_id VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT questions_passage_same_bank_fk
        FOREIGN KEY (bank_id, passage_group_id)
        REFERENCES passages(bank_id, passage_group_id)
        ON DELETE RESTRICT,
    CONSTRAINT grammar_fill_options_null
        CHECK (type <> 'grammar_fill' OR options IS NULL),
    CONSTRAINT cloze_options_four
        CHECK (type <> 'cloze' OR jsonb_array_length(options) = 4),
    CONSTRAINT gap_fill_options_seven
        CHECK (type <> 'gap_fill' OR jsonb_array_length(options) = 7),
    UNIQUE (bank_id, id)
);

CREATE INDEX questions_bank_type_status_idx ON questions (bank_id, type, status);
CREATE INDEX questions_bank_passage_idx ON questions (bank_id, passage_group_id);
CREATE INDEX questions_knowledge_points_gin ON questions USING GIN (knowledge_points);
CREATE INDEX questions_grammar_tags_gin ON questions USING GIN (grammar_tags);

CREATE TABLE practice_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL,
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    bank_name VARCHAR(80) NOT NULL,
    bank_version INTEGER NOT NULL DEFAULT 1,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes IN (30, 60)),
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'submitted', 'expired')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deadline TIMESTAMPTZ NOT NULL,
    submitted_at TIMESTAMPTZ,
    composition_note JSONB NOT NULL,
    UNIQUE (id, bank_id),
    CHECK (deadline > started_at),
    CHECK (status <> 'submitted' OR submitted_at IS NOT NULL)
);

CREATE INDEX practice_sessions_student_idx
    ON practice_sessions (student_id, started_at DESC);
CREATE INDEX practice_sessions_due_idx
    ON practice_sessions (status, deadline);

CREATE TABLE session_items (
    session_id UUID NOT NULL,
    question_id VARCHAR(100) NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    bank_id UUID NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (session_id, question_id),
    UNIQUE (session_id, ordinal),
    CONSTRAINT session_items_session_bank_fk
        FOREIGN KEY (session_id, bank_id)
        REFERENCES practice_sessions(id, bank_id)
        ON DELETE RESTRICT,
    CONSTRAINT session_items_question_bank_fk
        FOREIGN KEY (bank_id, question_id)
        REFERENCES questions(bank_id, id)
        ON DELETE RESTRICT
);

CREATE TABLE saved_answers (
    session_id UUID NOT NULL,
    question_id VARCHAR(100) NOT NULL,
    answer JSONB NOT NULL,
    client_revision BIGINT NOT NULL DEFAULT 0 CHECK (client_revision >= 0),
    saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (session_id, question_id),
    FOREIGN KEY (session_id, question_id)
        REFERENCES session_items(session_id, question_id)
        ON DELETE RESTRICT
);

CREATE TABLE error_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL,
    question_id VARCHAR(100) NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    question_type VARCHAR(20) NOT NULL,
    knowledge_points TEXT[] NOT NULL CHECK (cardinality(knowledge_points) > 0),
    grammar_tags TEXT[] NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'mastered')),
    streak SMALLINT NOT NULL DEFAULT 0 CHECK (streak BETWEEN 0 AND 2),
    activated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    mastered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (student_id, question_id, bank_id)
);

CREATE INDEX error_tags_student_bank_status_idx
    ON error_tags (student_id, bank_id, status);
CREATE INDEX error_tags_student_kp_gin
    ON error_tags USING GIN (knowledge_points);
CREATE INDEX error_tags_student_grammar_gin
    ON error_tags USING GIN (grammar_tags);

CREATE TABLE error_tag_successes (
    tag_id UUID NOT NULL REFERENCES error_tags(id) ON DELETE RESTRICT,
    session_id UUID NOT NULL REFERENCES practice_sessions(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tag_id, session_id)
);

CREATE TABLE knowledge_mastery (
    student_id UUID NOT NULL,
    knowledge_point TEXT NOT NULL,
    ewma NUMERIC(6, 5) NOT NULL CHECK (ewma BETWEEN 0 AND 1),
    attempt_count INTEGER NOT NULL CHECK (attempt_count >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, knowledge_point)
);

CREATE TABLE practice_reports (
    session_id UUID PRIMARY KEY REFERENCES practice_sessions(id) ON DELETE RESTRICT,
    student_id UUID NOT NULL,
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    bank_name VARCHAR(80) NOT NULL,
    report JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX practice_reports_student_idx
    ON practice_reports (student_id, created_at DESC);

CREATE TABLE rejected_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    generation_job_id UUID NOT NULL REFERENCES generation_jobs(id) ON DELETE RESTRICT,
    batch_id VARCHAR(100) NOT NULL,
    raw_item JSONB NOT NULL,
    rejection_reasons TEXT[] NOT NULL CHECK (cardinality(rejection_reasons) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bank_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bank_id UUID NOT NULL REFERENCES question_banks(id) ON DELETE RESTRICT,
    action VARCHAR(40) NOT NULL,
    previous_bank_id UUID REFERENCES question_banks(id) ON DELETE RESTRICT,
    actor VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX bank_audit_logs_bank_idx ON bank_audit_logs (bank_id, created_at DESC);

CREATE TABLE bank_active_state (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    active_bank_id UUID REFERENCES question_banks(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION enforce_single_active_bank()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'active' AND (TG_OP = 'INSERT' OR OLD.status <> 'active') THEN
        UPDATE question_banks
        SET status = 'ready'
        WHERE status = 'active' AND id <> NEW.id;
        UPDATE bank_active_state
        SET active_bank_id = NEW.id, updated_at = now()
        WHERE singleton = TRUE;
    ELSIF NEW.status <> 'active' AND (TG_OP = 'UPDATE' AND OLD.status = 'active') THEN
        UPDATE bank_active_state
        SET active_bank_id = NULL, updated_at = now()
        WHERE singleton = TRUE AND active_bank_id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER question_banks_single_active
BEFORE INSERT OR UPDATE OF status ON question_banks
FOR EACH ROW EXECUTE FUNCTION enforce_single_active_bank();

INSERT INTO bank_active_state (singleton, active_bank_id)
VALUES (TRUE, NULL)
ON CONFLICT (singleton) DO NOTHING;

CREATE OR REPLACE FUNCTION prevent_bank_append()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM question_banks
        WHERE id = NEW.bank_id
          AND status IN ('reviewing', 'ready', 'active', 'archived')
    ) THEN
        RAISE EXCEPTION 'BANK_APPEND_FORBIDDEN';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER passages_prevent_append
BEFORE INSERT ON passages
FOR EACH ROW EXECUTE FUNCTION prevent_bank_append();

CREATE TRIGGER questions_prevent_append
BEFORE INSERT ON questions
FOR EACH ROW EXECUTE FUNCTION prevent_bank_append();

COMMIT;
