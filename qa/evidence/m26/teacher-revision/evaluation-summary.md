# Teacher Revision Evaluation

Source SHA-256:
`63C27ABDC4275DF9B0EE0509A6DC915375F0A33CF200AB5CC281EA72189CCE5B`

## Verdict

The revised content is substantially better than the prior version, but it is
not Stage A ready and must not replace the six Bank rows yet.

The source is a Markdown teacher copy. It is not directly importable because it
does not carry `book_source`, `difficulty`, full assignment metadata, or an
explicit `evidence_sentence` field. The machine evaluation below maps those
fields from the original Stage A records only for review.

## Machine gate results

| Passage | Words | Flesch | Result | Blocking issues |
| --- | ---: | ---: | --- | --- |
| CLOZE-01 | 251 | 68.49 | fail | average sentence length 14.76 < 15; 6 unique out-of-list words; Q2/Q4 explanations have 2 sentences |
| CLOZE-02 | 277 | 75.16 | fail | `buying` leaks through `buy`; Flesch 75.16 > 70; only 1 sentence has >=22 words; 5 unique out-of-list words |
| GRAMMAR-01 | 191 | n/a | fail | all 10 blanks use `(1)...(10)` instead of circled `①...⑩` |
| READING-01 | 324 | 66.63 | fail | 10 unique out-of-list words |
| READING-02 | 300 | 64.71 | fail | 26 unique out-of-list words |
| GAP-01 | 201 | n/a | fail | word count 201 < 220; 6 unique out-of-list words; all 5 explanations have only 2 sentences |

Out-of-list examples:

- CLOZE-01: `cannot`, `cope`, `foolish`, `overnight`, `revision`, `sensible`.
- CLOZE-02: `complaint`, `forgotten`, `lin`, `twenty-three`, `wei`.
- READING-01: `cannot`, `disagreed`, `explanations`, `fifteen-year-olds`,
  `installed`, `log`, `noticeably`, `productive`, `twice`, `westfield`.
- READING-02: 26 unique words including `kilns`, `cement`, `conservators`,
  `maintenance`, `provincial`, `gauges`, and the named entities `anhe`,
  `ming`, `chen`, and `rui`.
- GAP-01: `assembly`, `council`, `council's`, `enthusiasm`, `kilogram`, `threw`.

## Pro judge

- All six passages were judged coherent.
- All 53 questions were judged to have one clear best answer.
- Reading evidence and option rewriting were accepted by Pro after the
  evidence sentences were reconstructed for evaluation.
- R13 near-synonym requirement fails for both cloze passages: Pro identified
  0 such items in each passage, while the requirement is at least 2.

## Additional content concerns

- CLOZE-02 blank 2 uses `a shop lives on trust rather than on speed`; the
  contrast is understandable but unnatural and not a strong teaching model.
- CLOZE-02 uses the invented personal name `Lin Wei`.
- READING-01 uses the named school `Westfield High`.
- READING-02 uses named place/person forms `Anhe`, `Ming`, and `Chen Rui`.
- Under the previously retained R10 wording, 48/53 explanations fail because
  the final sentence is `本题考查……`, not an explicit explanation of two
  distractors. The five gap-fill explanations do reference wrong option letters
  in their final sentence.

## What can be reused

- The overall scenario and structure are usable as editorial direction.
- Reading-01 and Reading-02 are much stronger than before.
- Grammar item design is coherent after changing blank markers.
- Gap-fill sentence-boundary design is sound; it mainly needs length and
  explanation-format repair.

## What must change before acceptance

1. Return JSON using the Stage A record contract, including all metadata and
   reading `evidence_sentence`.
2. Convert grammar blanks to `① ______` ... `⑩ ______`.
3. Bring all passages within the current word, Flesch, sentence-length,
   long-sentence, and vocabulary limits.
4. Remove all answer-word/inflection leaks; specifically CLOZE-02 Q9.
5. Supply at least two genuine near-synonym cloze questions per passage.
6. Make every explanation at least three sentences and put the two-distractor
   explanation in the final sentence where R10 remains applicable.
