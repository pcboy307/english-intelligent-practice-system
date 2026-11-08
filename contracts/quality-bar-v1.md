# M2 Quality Bar v1

## Mandatory gates

- R1: every answer is exactly one of the four (or seven) displayed options.
- R2: cloze options are four different words; repeated lemmas are rejected.
- R3: no cloze option, including an inflected form, appears in its stem.
- R4: reading questions must be comprehension questions, never grammar or
  meta-language identification.
- R5: every reading question includes `evidence_sentence`, an exact substring
  of the passage.
- R6: passage vocabulary is checked against the frozen whitelist using the
  frozen inflection/derivation normalization contract; every normalization is
  logged.
- R7: the full bank matches exact type, difficulty, book-tag and topic quotas.
- R8: Pro judges the whole cloze passage as coherent prose, not assembled
  sentences.
- R9: Pro must identify one clearly best option; `NO_CLEAR_BEST` is rejected.
- R10: every explanation ends with one explicit sentence naming why the two main
  distractors are wrong.

## Observation-only gates

- G13: direct synonym/antonym/root clues are recorded but do not block.
- G14: clue distance is recorded but does not block.
- G15: 6 easy / 6 medium / 3 hard is recorded but does not block.
- G16: Flesch Reading Ease is recorded but does not block.

These observation items cannot override R1-R10.

## Type rules

- Cloze: 15 blanks, four options, one coherent paragraph, at most three
  recurring characters, a timeline, and no morphology-only choices.
- Grammar fill: 10 four-option blanks; distractors belong to the same grammar
  category.
- Reading: four comprehension questions per passage; the five subskills are
  balanced to 20 each across 25 passages.
- Gap fill: five blanks with seven mutually distinguishable options; four
  cohesion types are covered across ten passages.

## Composition

- 47 passages / 300 questions:
  cloze 6x15=90, grammar 6x10=60, reading 25x4=100, gap fill 10x5=50.
- Difficulty: 45/90/105/45/15 for levels 1-5.
- Cloze + grammar book tags: 选必二 68, 选必一 45, 必修 30, 跨册 7.
- Reading + gap fill elective-topic questions: at least 75.
- Cloze targets: each of 45 high-frequency words appears exactly twice.
- Grammar: all 21 whitelist IDs covered about three times each.
- Reading: five question types, 20 each.
- Gap fill: four cohesion types covered across all blanks.

## Run controls

- Batch size is at most 12 passages.
- A failed passage is recorded and skipped; it does not terminate the batch.
- Stop only for authentication failure, unsupported API capability, a run cost
  above CNY 5, or all passages failing for the same systemic reason.
- Raw request state, token usage, finish reason, failure category and cost are
  retained under `qa/evidence/m2/`.
