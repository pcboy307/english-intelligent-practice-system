BEGIN;

ALTER TABLE questions
    DROP CONSTRAINT grammar_fill_options_null;

ALTER TABLE questions
    ADD CONSTRAINT grammar_fill_options_four
    CHECK (
        type <> 'grammar_fill'
        OR (
            jsonb_typeof(options) = 'array'
            AND jsonb_array_length(options) = 4
        )
    );

COMMIT;
