# M2.6 Stage A Result

## Outcome

- passages: 6/6
- questions: 53/53
- all R11-R15 and DeepSeek Pro audits passed
- Bank: `20261108_500`
- Bank ID: `ec6ba83b-ef27-4b36-8dc0-d2181a8325f8`
- Bank status after browser verification: `generating`
- old active bank restored: `M2 Bank #2`

## Passage results

| Passage | Type | Questions | Words | Flesch | R11 |
| --- | --- | ---: | ---: | ---: | --- |
| M26-A-CLOZE-01 | cloze | 15 | 212 | 65.56 | pass |
| M26-A-CLOZE-02 | cloze | 15 | 219 | 60.06 | pass |
| M26-A-GRAMMAR-01 | grammar_fill | 10 | 215 | n/a | pass |
| M26-A-READING-01 | reading | 4 | 264 | 58.78 | n/a |
| M26-A-READING-02 | reading | 4 | 258 | 57.68 | n/a |
| M26-A-GAP-01 | gap_fill | 5 | 283 | n/a | pass |

R12 checks:

- both cloze passages meet average sentence length, long-sentence, complex
  structure, and Flesch requirements;
- grammar covers six categories: article, noun clause, relative clause,
  tense/voice, adverbial clause, and non-finite;
- both readings meet average sentence and Flesch requirements;
- gap fill covers all five cohesion types.

R13 checks:

- Pro judge reports unique best answer for all 53 items;
- both cloze passages use same-part-of-speech, same-semantic-field options;
- two calibrated near-synonym questions per cloze are recorded in the gate JSON.

R14 checks:

- both readings use main idea, inference, purpose/attitude, and vocabulary in
  context;
- every evidence sentence is a passage substring;
- no answer copies five consecutive passage words;
- no meta-language grammar question.

R15 checks:

- six distinct topics: health/mental health, career, family generations,
  technology, historical heritage, environment;
- allowed topic count: 6/6;
- no topic exceeds six passages.

## Cost

- final resumed run: ¥0.504281
- final successful build projection: ¥2.85 for 300 questions,
  ¥19.03 for 2000 questions
- all Stage A attempts, deduplicated by request ID: ¥6.068438
- all-attempt projection: ¥34.35 for 300, ¥229.00 for 2000
- request failures excluding `ok`: 222/1106 = 20.07%
- `finish_reason=length`: 17/1106 = 1.54%

## Browser

- actual web app opened with a 29-question Stage A paper;
- cloze and grammar passages rendered with underline-only blanks;
- test session was deleted after capture;
- active bank was restored to `M2 Bank #2`.

Screenshots:

- `blank-render.png`
- `grammar-render.png`

## Validation

```text
pytest: 141 passed, 1 warning
M0_CHECK=PASS
API_CONTRACT_CHECK=PASS calls=20
contracts/openapi.yaml is valid
TypeScript tsc --noEmit: PASS
migration 004 reapply: PASS
```
