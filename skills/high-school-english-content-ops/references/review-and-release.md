# Review and Release

## Review Severity

- `BLOCKER`: wrong answer, no correct option, duplicate answer, answer leakage, broken JSON, impossible placeholder contract.
- `HIGH`: ambiguous best answer, invalid inserted sentence, explanation cites nonexistent text, semantic book/grammar mismatch.
- `MEDIUM`: implausible distractors, repeated template structure, weak passage coherence, inconsistent difficulty.
- `LOW`: naming, formatting, non-blocking readability issues.

Every finding needs a passage ID, question number where applicable, rule, and raw evidence.

## Semantic Integrity

Check that the fields describe the content:

- Tags are chosen from the actual tested grammar, not used as distribution padding.
- `book_source` matches the content origin; do not derive it solely from the grammar intersection.
- Reading and seven-choice tags describe comprehension or cohesion, not unrelated grammar.
- Knowledge points are natural Chinese usable in a student report.

## Import and Activation

- Confirm Bank name uniqueness.
- Verify actual `target_size` and `composition`.
- Verify passage/question counts after import.
- Verify the active Bank and Coverage snapshot.
- Keep prior Bank history immutable.
- Imported revisions must be distinguishable from their source bank.

## Release Evidence

Record:

- Commit and version.
- Active Bank ID, name, status.
- Passage/question counts.
- Type, difficulty, book and topic distributions.
- Machine-gate result.
- Pro/human sample result.
- Browser flow or API evidence.
- Known failures and deferred items as `not verified` where applicable.

## Practice Acceptance

- Selection returns one cloze, one grammar-fill, and one reading or seven-choice passage.
- Selection minimizes total passage coverage, then maximizes distinct topics.
- Pre-submit responses contain no answer or explanation.
- Submit is idempotent.
- Report returns score, type accuracy, weak points, and per-question explanations.
- Review mode returns the saved answer, correctness, and explanation only after submission.
- Browser navigation and scroll position match the user-visible contract.
