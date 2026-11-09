# Content Generation

## Before a Model Call

- Resolve the active bank, target size, passage type, question count, word range, difficulty, topic, and book source.
- Read the exact JSON Schema; do not restate a simplified schema from memory.
- Load the vocabulary whitelist and grammar/book matrix.
- Reject internally inconsistent numeric requirements before spending tokens.

## Generation Sequence

1. Generate only the passage skeleton.
2. Validate placeholder count, numbering, word count, syntax, vocabulary, and answer leakage.
3. Generate questions against the fixed passage.
4. Inject fixed `answer_target` values where assigned.
5. Generate distractors in the same grammar or semantic category.
6. Generate explanations only after the questions and answers are fixed.
7. Validate the complete record immediately before persistence.
8. Run Pro/human semantic review.

## Content Checks

### Cloze

- Exactly 15 blanks and four distinct options per blank.
- Same part of speech and comparable form level.
- One clearly best answer supported by context.
- No answer, inflection, or option leakage in the passage.
- Do not accept three absurd distractors as “easy” quality.

### Grammar Fill

- Exactly 10 four-option items.
- Options belong to the same grammar category.
- Substitute the answer back into the sentence.
- `grammar_tags` and `book_source` must describe the actual sentence, not merely satisfy quotas.

### Reading

- Four comprehension questions, not grammar-identification questions.
- `evidence_sentence` must be an exact passage substring.
- Answer text must not copy a long contiguous span from the passage.
- Check question types and at least one paragraph-function item for M2.6.

### Seven-choice

- Five blanks and seven distinct shared options.
- Three or more cohesion types per passage.
- No six-word contiguous overlap between an option and the passage.

## Explanation Contract

- Chinese, at least three sentences.
- Explain the correct answer from the actual passage.
- Explain the two principal distractors.
- Do not quote a phrase absent from the passage.
- Do not introduce facts not present in the source.

## Repair Rules

- Preserve `passage_group_id` unless the user explicitly requests a new unit.
- Change only defective fields where possible.
- Mark edited passages for full revalidation.
- Never lower a gate or change the Schema to make a defective record pass.
