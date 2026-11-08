-- M2.6 aligns passage ceilings with the Guangdong upper-secondary profile.
ALTER TABLE passages
    DROP CONSTRAINT IF EXISTS passage_word_limit;

ALTER TABLE passages
    ADD CONSTRAINT passage_word_limit CHECK (
        word_count <= CASE type
            WHEN 'cloze' THEN 290
            WHEN 'grammar_fill' THEN 220
            WHEN 'reading' THEN 380
            WHEN 'gap_fill' THEN 350
            ELSE NULL
        END
    );
