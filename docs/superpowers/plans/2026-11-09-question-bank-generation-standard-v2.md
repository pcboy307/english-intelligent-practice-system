# Question Bank Generation Standard v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Freeze the adjudicated question-bank generation rules in one model-readable standard and align the import contract and validators with it.

**Architecture:** Keep `bank-v1` as the import/export envelope, make M2.6 full-bank quotas mechanically enforceable, and separate automatic checks from Pro/manual gates. Publish one authoritative Markdown standard that covers both generation and round-trip review.

**Tech Stack:** JSON Schema 2020-12, FastAPI import normalizer, pytest, Python 3.12.

**Spec:** `generation-standard-adjudication.md` plus Codex's accepted/partial/rejected adjudication from 2026-11-09.

## Global Constraints

- M2.6 full-bank composition is 72 passages / 500 questions.
- M2.6 question-level difficulty is 60/120/190/95/35.
- M2.6 all-question book distribution is 225/150/100/25.
- `m26-v1` requires 500 questions, 72 passages, and every passage to use `validation_profile: "m26"`.
- `bank-v1` does not enforce full-bank quota, but each generated passage is still validated by its declared profile.
- Grammar fill placeholders are `①–⑩`; cloze and gap fill placeholders are `(1)–(5/15)`.
- Generated files never use `validation_profile: "stored"`; `stored` is reserved for exported banks.
- Do not modify unrelated M2/M2.6 evidence or generation work.

---

### Task 1: Fix M2.6 quota contract and profile enforcement

**Files:**
- Modify: `contracts/m26-generation-params-v2.json`
- Modify: `backend/app/bank_transfer.py`
- Test: `tests/generation/test_m26_quality.py`
- Test: `tests/api/test_bank_import_delete.py`

**Interfaces:**
- Produces: `M26_TARGET_SIZE`, `M26_COMPOSITION_TARGETS`, `M26_DIFFICULTY_TARGETS`, `M26_BOOK_TARGETS`, `M26_ALLOWED_TOPICS` loaded from the M2.6 contract.
- Produces: import error `M26_PROFILE_MISMATCH`.

- [x] **Step 1: Write failing quota and profile tests**

```python
def test_m26_book_targets_cover_all_500_questions():
    from backend.app.bank_transfer import M26_BOOK_TARGETS

    assert M26_BOOK_TARGETS == {
        "选必二": 225,
        "选必一": 150,
        "必修": 100,
        "跨册": 25,
    }
    assert sum(M26_BOOK_TARGETS.values()) == 500
```

- [x] **Step 2: Run the focused tests and confirm the old 250 total fails**

- [x] **Step 3: Add quota values to the M2.6 contract and load them in the importer**

- [x] **Step 4: Reject `m26-v1` packages containing a non-`m26` passage profile**

- [ ] **Step 5: Run quota/profile tests and commit**

### Task 2: Freeze enum and text formats in the import Schema

**Files:**
- Modify: `contracts/schemas/bank-import-package.json`
- Modify: `backend/app/bank_transfer.py`
- Test: `tests/api/test_bank_import_delete.py`
- Test: `tests/generation/test_m2_generation_config.py`

**Interfaces:**
- Produces: canonical `book_source` forms `必修1 U1`, `选必一 U1`, `选必二 U1`, `跨册综合`.
- Produces: canonical `grammar_category` values and documented legacy aliases.
- Produces: bounded `cohesion_type` values for M2 and M2.6.

- [x] **Step 1: Write failing Schema/import tests for invalid book source and grammar category**

- [x] **Step 2: Run tests and confirm current free-form strings are accepted**

- [x] **Step 3: Add Schema defs/enums and importer validation**

- [ ] **Step 4: Run Schema and import tests and commit**

### Task 3: Publish one authoritative generation and round-trip standard

**Files:**
- Move/replace: `docs/llm-question-bank-single-file-prompt.md` → `docs/question-bank-generation-standard-v2.md`
- Modify: `contracts/quality-bar-v1.md`
- Modify: `docs/bank-import-export-format.md`
- Modify: `contracts/config-spec.md`
- Test: `tests/generation/test_m2_generation_config.py`

**Interfaces:**
- Produces: one Markdown file accepted by an LLM for fresh generation, export review, and edited export re-import.

- [x] **Step 1: Add a failing documentation contract test for required headings and forbidden legacy wording**

- [x] **Step 2: Write the v2 standard with exact envelope, quality gates, M2.6 quotas, placeholder rules, review workflow, and final checklist**

- [x] **Step 3: Update quality/config documents to point to the single standard**

- [ ] **Step 4: Run documentation tests and commit**

### Task 4: End-to-end verification

**Files:**
- Verify: M0 contract checks, API contract checks, OpenAPI, TypeScript, focused tests.

- [x] **Step 1: Run focused M2.6/import tests**

- [ ] **Step 2: Run `check-m0.ps1` and `check-api-contract.ps1`**

- [x] **Step 3: Validate OpenAPI and TypeScript**

- [x] **Step 4: Preview a real six-passage package through the import endpoint**

- [ ] **Step 5: Run `git diff --check` and commit only the standard/contract changes**
