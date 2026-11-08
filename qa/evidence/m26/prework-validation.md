# M2.6 Stage A Prework Validation

Date: 2026-11-08

## Regression tests

The following tests exercise the real pre-persist validator:

| Test | Bad input | Required rejection |
| --- | --- | --- |
| `test_rejects_answer_word_printed_at_its_own_blank` | `(1) anxious` | `PLACEHOLDER_ANSWER_WORD_LEAK` |
| `test_rejects_blank_marker_followed_by_an_ordinary_word` | `(1) suddenly` | `PLACEHOLDER_MISSING` |
| `test_rejects_placeholder_with_a_remaining_word_fragment` | `(1) graduat______` | `PLACEHOLDER_FRAGMENT` |
| `test_rejects_gap_option_text_leaking_into_the_passage` | option and passage share six contiguous words | `GAP_OPTION_TEXT_LEAK` |
| `test_accepts_a_uniform_placeholder_after_every_marker` | `(1) ______` ... `(15) ______` | no integrity failure |
| `test_rejects_an_inflected_answer_form_elsewhere_in_the_passage` | answer `wait`; passage contains `waited` | `ANSWER_WORD_APPEARS_IN_PASSAGE` |
| `test_revalidates_the_text_after_the_json_render_boundary` | renderer text changes `______` to `anxious` | same answer-leak rejection |
| `test_prevalidated_insert_cannot_bypass_placeholder_integrity` | bad record passed with `prevalidated=True` | rejected before any row is written |

Focused result:

```text
........                                                                 [100%]
8 passed in 0.78s
```

Full suite:

```text
141 passed, 1 warning
```

The warning is the pre-existing Starlette `BlockingPortal` deprecation.

## Enforcement points

- The passage request rejects missing, answer-occupied, fragmented, or
  non-uniform placeholders before question generation.
- The complete record gate checks every answer against the passage using the
  frozen lemma resolver, and rejects seven-choice options with any six-word
  contiguous passage overlap.
- `M2Repository.insert_passage` and `replace_passage_questions` always run the
  complete validator immediately before writes. `prevalidated=True` no longer
  bypasses validation.
- `validate_rendered_passage` applies the same checks at the JSON render
  boundary. Stage A will additionally capture browser screenshots.

## One-time corrected impact summary

| Defect state | Blanks | Passages |
| --- | ---: | ---: |
| Answer occupies its own blank | 15 | 1 |
| Missing placeholder with a non-answer word | 74 | 8 |
| Open-class answer form appears anywhere | 20 | 6 |
| Seven-choice option has at least six contiguous passage words | n/a | 6 |

The open-class count excludes grammar function words. This summary supersedes
the broader exploratory counts in the Stage 0 report and is not a repair plan
for the old bank.

## Database state

- Active bank remains `M2 Bank #2`, `active`, 300 published questions.
- No bank named `20261108_500` exists.
- No old passage status or content was changed.
- No Stage A generation request was sent.

## Contract checks

```text
M0_CHECK=PASS
API_CONTRACT_CHECK=PASS calls=20
contracts/openapi.yaml is valid
TypeScript tsc --noEmit: PASS
```
