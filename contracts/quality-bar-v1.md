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
- R11: for cloze and grammar fill, the answer and its exact/inflected forms must
  occur zero times anywhere in the passage; derived forms are not counted.
- R12: M2.6 word-count ranges, composition, difficulty and book-tag totals are
  hard limits from `contracts/m26-generation-params-v2.json`.

## Observation-only gates

- G13: direct synonym/antonym/root clues are recorded but do not block.
- G14: clue distance is recorded but does not block.
- G15: 6 easy / 6 medium / 3 hard is recorded but does not block.
- G16: Flesch Reading Ease is recorded but does not block.

These observation items cannot override R1-R12.

## Pro and human gates

- Every cloze and grammar-fill answer must be substituted back into its sentence.
  The resulting sentence must be grammatical and semantically valid.
- All options for one blank must have the same word class and inflection level.
- A Pro judge or human reviewer must reject any passage with an invalid rendered
  sentence, an ambiguous answer, or more than one defensible option.
- These checks are not claimed as complete machine validation.

## Type rules

- Cloze: 15 blanks, four options, one coherent paragraph, at most three
  recurring characters, a timeline, and no morphology-only choices.
- Grammar fill: 10 four-option blanks; distractors belong to the same grammar
  category.
- Reading: four comprehension questions per passage; the five subskills are
  balanced to 20 each across 25 passages.
- Gap fill: five blanks with seven mutually distinguishable options; four
  cohesion types are covered across ten passages.

## M2.6 generation parameters v2

The machine-readable source of truth is
`contracts/m26-generation-params-v2.json`.

- Cloze: 280-320 words; at least four sentences of at least 25 words; at
  least three of non-finite, nominal clause, parenthetical/appositive, and
  inversion/ellipsis; at least three near-synonym discrimination items;
  Flesch 45-60.
- Grammar fill: 220-260 words; all ten items must include perfect/passive
  non-finite, preposition + which, a what-led nominal clause, subjunctive, and
  inversion.
- Reading: 350-420 words; average sentence length at least 20; Flesch 45-60;
  every passage includes at least one paragraph-function question.
- Gap fill: 320-380 words; expository or argumentative prose on an abstract
  topic such as technology ethics, urban governance, or a psychological
  mechanism.
- Vocabulary remains governed by the frozen whitelist; abstract nouns are
  allowed when they are in scope or clarified by context.

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
- M2.6 complete banks are 72 passages / 500 questions:
  cloze 12x15=180, grammar 12x10=120, reading 40x4=160, gap fill 8x5=40.
- M2.6 question-level difficulty is 60/120/190/95/35.
- M2.6 all-question book tags are 225/150/100/25, totaling 500.

## Run controls

- One model response generates one passage; valid passages are merged locally.
- A `m26-v1` package must contain only `validation_profile: "m26"` passages.
- A `bank-v1` package does not enforce 300/500 full-bank quotas.
- A failed passage is recorded and skipped; it does not terminate the batch.
- Stop only for authentication failure, unsupported API capability, a run cost
  above CNY 5, or all passages failing for the same systemic reason.
- Raw request state, token usage, finish reason, failure category and cost are
  retained under `qa/evidence/m2/`.
