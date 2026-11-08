# M2.6 Pre-Stage-A Audit

Date: 2026-11-08

## A. Original persistence path

`scripts/run-m2-full.py` currently materializes passage text at:

```python
record = {
    "type": spec["type"],
    "passage_group_id": spec["passage_group_id"],
    "topic": spec["topic"],
    "book_source": spec["book_source"],
    "difficulty": spec["difficulty"],
    "passage": str(data.get("passage", "")),
    "questions": questions,
}
```

The generated record is saved through:

```python
repository.insert_passage(
    bank_id=bank["id"],
    job_id=job["id"],
    batch_id=BATCH_ID,
    record=result["record"],
    prevalidated=True,
)
```

`M2Repository.insert_passage` always calls `_reject_invalid_record` before any
write. There are no direct `INSERT` or `UPDATE` statements for `passages` or
`questions` in `run-m2-full.py`.

The former direct `DELETE` statements were also moved into
`M2Repository.clear_bank_content`; the script now contains no direct DML
against `passages` or `questions`.

## B. Inflection matching

Answer leakage uses a one-step resolver over the frozen
`contracts/vocabulary-normalization.json`:

- exact forms;
- the irregular inflection table;
- regular plural, past, participle, third-person, comparative, superlative,
  and possessive rules.

Derivational rules such as `-ment`, `-ity`, `-ly`, `-ful`, and agent `-er` are
not used for answer leakage. This avoids treating a related derived word as the
answer itself.

| Answer | Passage form | Result |
| --- | --- | --- |
| `achieve` | `achievement` | not a leak |
| `succeed` | `success` | not a leak |
| `confident` | `confidence` | not a leak |
| `achieve` | `achieved` | leak |

Across the existing 47 passages:

- production expression-level rule: 38 blanks / 8 passages;
- same rule with closed-class answer tokens excluded: 27 blanks / 7 passages;
- Stage 0 literal open-class audit: 20 blanks / 6 passages.

The difference is primarily accepted inflections such as
`encourage -> encouraged`; the production count also includes closed-class
answers unless the comparison explicitly excludes them.

## C. Calibrating the validator

Known-bad sample:

- `M2-FULL-CLOZE-04`: rejected.
- Codes include `PLACEHOLDER_ANSWER_WORD_LEAK` and
  `ANSWER_WORD_APPEARS_IN_PASSAGE`.

Known-good sample:

- `M2-FULL-GAP-10`: accepted with no machine failures.

Full 47-passage result:

- blocked: 37
- allowed: 10
- all 9 known-bad passages were blocked
- no accepted fill passage has an invalid blank

Blocked passage IDs:

`M2-FULL-CLOZE-01`, `M2-FULL-CLOZE-02`, `M2-FULL-CLOZE-03`,
`M2-FULL-CLOZE-04`, `M2-FULL-CLOZE-05`, `M2-FULL-CLOZE-06`,
`M2-FULL-GAP-01`, `M2-FULL-GAP-02`, `M2-FULL-GAP-03`,
`M2-FULL-GAP-04`, `M2-FULL-GAP-05`, `M2-FULL-GAP-06`,
`M2-FULL-GAP-07`, `M2-FULL-GAP-08`, `M2-FULL-GAP-09`,
`M2-FULL-GRAMMAR-01`, `M2-FULL-GRAMMAR-02`, `M2-FULL-GRAMMAR-03`,
`M2-FULL-GRAMMAR-04`, `M2-FULL-GRAMMAR-05`, `M2-FULL-GRAMMAR-06`,
`M2-FULL-READING-01`, `M2-FULL-READING-03`, `M2-FULL-READING-04`,
`M2-FULL-READING-07`, `M2-FULL-READING-08`, `M2-FULL-READING-09`,
`M2-FULL-READING-11`, `M2-FULL-READING-13`, `M2-FULL-READING-14`,
`M2-FULL-READING-17`, `M2-FULL-READING-18`, `M2-FULL-READING-19`,
`M2-FULL-READING-20`, `M2-FULL-READING-22`, `M2-FULL-READING-23`,
`M2-FULL-READING-24`.

Allowed passage IDs:

`M2-FULL-GAP-10`, `M2-FULL-READING-02`, `M2-FULL-READING-05`,
`M2-FULL-READING-06`, `M2-FULL-READING-10`, `M2-FULL-READING-12`,
`M2-FULL-READING-15`, `M2-FULL-READING-16`, `M2-FULL-READING-21`,
`M2-FULL-READING-25`.
