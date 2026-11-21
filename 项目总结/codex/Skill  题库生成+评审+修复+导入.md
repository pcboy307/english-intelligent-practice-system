---
name: high-school-english-content-ops
description: Generate, review, repair, import, or release schema-compliant high-school English question banks for this Expo/FastAPI practice system. Use when work involves curriculum alignment, grammar/vocabulary quotas, AI content gates, bank migration, practice selection, or release evidence; do not use for unrelated English tutoring.
---

# High School English Content Ops

Work from the repository's machine contracts and current runtime state. This skill preserves the project-specific decisions that are not obvious from the code.

## Start Here

Read only what the task needs:

1. Current version: `contracts/VERSION`.
2. Content authority: `docs/question-bank-generation-standard-v2.md`.
3. Machine schemas: `contracts/schemas/` and `contracts/openapi.yaml`.
4. Curriculum and vocabulary: `contracts/curriculum.json`, `contracts/vocabulary-whitelist.json`.
5. Current selection rules: `config/practice-modes.json`, `backend/app/composer.py`.
6. Historical decisions: `CHANGELOG.md` and the relevant file under `docs/change-log/`.

Do not infer current quotas, bank size, active bank, or model configuration from memory.

## Route the Task

- **Generate**: create one passage and its complete questions, validate it, then merge through deterministic tooling. Read [references/content-generation.md](references/content-generation.md).
- **Review**: report evidence-backed defects without silently rewriting content. Read [references/review-and-release.md](references/review-and-release.md).
- **Repair**: preserve valid passage IDs and structure, change only the requested content, and output a complete re-importable package.
- **Import/release**: verify active Bank, quotas, coverage, semantic checks, and evidence. Read [references/review-and-release.md](references/review-and-release.md).
- **Application behavior**: distinguish content-contract bugs from UI/runtime bugs. Use OpenAPI-generated types and browser evidence.

## Non-Negotiable Invariants

- One model request generates one verifiable unit; never request a full 72-passage bank in one response.
- Machine validation and semantic validation are separate claims.
- Do not backfill `book_source`, grammar tags, evidence sentences, or knowledge labels merely to satisfy a gate.
- Keep the fixed answer when generating questions, explanations, or distractors unless the user explicitly requests a content rewrite.
- Explanations must be checked against the actual passage; a quoted phrase that is absent is a defect.
- The answer and its accepted inflected forms must not leak into the passage for cloze or grammar fill.
- Reading evidence must be an exact passage substring.
- Historical sessions, reports, mistakes, and coverage remain attached to their original Bank.
- Answers and explanations never enter pre-submit student responses.

## Validation

Use the repository's deterministic tools and tests rather than inventing equivalent checks:

```powershell
.\scripts\check-m0.ps1
.\scripts\check-api-contract.ps1
.\.venv\Scripts\python.exe -m pytest -q
C:\Users\Administrator\node24\npm.cmd run typecheck
```

For UI behavior, use `agent-browser` and capture the actual URL, visible elements, and relevant DOM dimensions/state. For content, retain rejected samples and failure categories.

## Output Discipline

- Lead with the outcome.
- Separate `passed`, `failed`, `not verified`, and `deferred`.
- Include reproducible commands or artifact paths.
- Never turn an observation gate into a hard gate or vice versa.
- If a change alters a frozen contract, add a change record and update the version through its single source.

## Supporting Assets

- Detailed generation and content gates: [references/content-generation.md](references/content-generation.md)
- Review, import, and release gates: [references/review-and-release.md](references/review-and-release.md)
- Reusable prompts: `docs/prompt-library/`
- Architecture and known limitations: `docs/architecture/system-overview.md`
