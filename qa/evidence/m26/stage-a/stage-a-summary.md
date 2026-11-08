# M2.6 Stage A Result

## Outcome

- generation parameter version: `2.6.1`
- prompt version: `m26-stage-a-v3.5`
- passages: 6/6
- questions: 53/53
- final machine and DeepSeek Pro gates: all passed
- bank: `20261108_500`
- bank ID: `70b53084-eb02-40db-9ee6-f986120679c7`
- bank status: `active` after switch verification
- coverage snapshot: present and switch activation verified
- known limitation: this is the 6-passage / 53-question Stage A sample bank;
  full-paper assembly remains governed by the normal paper quotas and is not
  guaranteed until Stage B provides the complete bank.
- previous bank after switch: `M2 Bank #2` (`ready`)

## Passage results

| Passage | Type | Questions | Words | Avg sentence | Flesch | Long sentences | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| M26-A-CLOZE-01 | cloze | 15 | 305 | 30.50 | 56.61 | 7 | pass |
| M26-A-CLOZE-02 | cloze | 15 | 295 | 21.07 | 52.96 | 5 | pass |
| M26-A-GRAMMAR-01 | grammar_fill | 10 | 259 | 21.58 | n/a | 3 | pass |
| M26-A-READING-01 | reading | 4 | 373 | 23.31 | 48.67 | 7 | pass |
| M26-A-READING-02 | reading | 4 | 397 | 30.54 | 51.60 | 10 | pass |
| M26-A-GAP-01 | gap_fill | 5 | 378 | 19.89 | n/a | 4 | pass |

## Parameter checks

- Both cloze passages use at least three distinct structures from non-finite,
  noun clause, parenthetical/appositive, and inversion/ellipsis.
- Cloze near-synonym discrimination counts are 3 and 4.
- Grammar fill includes all five mandatory categories:
  `non_finite_perfect_passive`, `preposition_plus_which`,
  `what_noun_clause`, `subjunctive`, and `inversion`.
- Both reading passages contain a `paragraph_function` question.
- Reading averages are 23.31 and 30.54 words; Flesch values are 48.67 and 51.60.
- Gap fill is a 378-word argumentative passage on technology ethics and
  algorithmic accountability.
- Both cloze passages contain exactly 15 placeholders; grammar fill contains
  exactly 10; gap fill contains exactly 5; reading passages contain 0.
- Pro judging verifies answer uniqueness, answer support, inserted-answer
  grammar, and inserted-answer semantics for every question.

## Structure repair found during review

An earlier v2 candidate was rejected after manual review because it contained
an extra 16th cloze marker and stray blank markers in reading passages. Those
cases are now permanent machine gates and have tests:

- `PLACEHOLDER_COUNT_INVALID`
- `UNEXPECTED_PLACEHOLDER_MARKER`
- `UNEXPECTED_PLACEHOLDER`

The rejected v2 evidence is archived under
`work/backups/m26-stage-a-v2-invalid-20261108.zip`.

## Cost

- current successful generation accounting: `CNY 0.583974`
- prompt tokens: `75,064`
- completion tokens: `25,361`

## Validation

```text
pytest: 163 passed, 1 warning
M0_CHECK=PASS
API_CONTRACT_CHECK=PASS calls=24
OpenAPI: PASS
TypeScript tsc --noEmit: PASS
migration 005 reapply: PASS
```
