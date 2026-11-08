BEGIN;

ALTER TABLE passages
    DROP CONSTRAINT IF EXISTS passage_word_limit;

ALTER TABLE passages
    ADD CONSTRAINT passage_word_limit CHECK (
        word_count <= CASE type
            WHEN 'cloze' THEN 320
            WHEN 'grammar_fill' THEN 260
            WHEN 'reading' THEN 420
            WHEN 'gap_fill' THEN 380
            ELSE NULL
        END
    );

COMMIT;
