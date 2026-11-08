BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS question_banks_name_ci_unique
    ON question_banks (lower(name));

COMMIT;
