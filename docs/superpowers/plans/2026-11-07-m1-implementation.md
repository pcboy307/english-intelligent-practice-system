# M1 最小闭环实施计划

> **For agentic workers:** Execute in strict serial order using `superpowers:executing-plans`. Do not dispatch implementation tasks in parallel. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可由 Docker Compose 启动、由 Expo 学生端真实完成 30/60 分钟练习、交卷报告与错题闭环的 M1 本地系统。

**Architecture:** FastAPI 单体按练习、报告、题库三个服务包分层，PostgreSQL 强制 Bank 隔离，Redis 承载生成 job 锁与短期状态；Expo App 只持有学生答案草稿和服务端 deadline，交卷后才接收解析。

**Tech Stack:** Node 24 LTS, Expo SDK 58, React Native, TypeScript, Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, PostgreSQL 16, Redis 7, pytest, Jest.

**Spec:** `docs/superpowers/specs/2026-11-07-high-school-english-practice-design.md`

## Global Constraints

- 25 个正式教材单元；词汇按词元计，语法按 ID 计。
- 只允许人教版 2019 必修 1–3 与选必 1–2；选必 3–4 一律超纲。
- 所有 Bank 隔离；组卷只从 `session.bank_id` 取题。
- 同一时刻最多一个 active Bank；切换只影响新会话。
- 标准 Bank 2000/315；M1 Demo Bank 60/11。
- M1 不验收 7 天重复率；M3 生效。
- 交卷前响应和 App 存储不得含答案或解析。
- 服务端 deadline 是唯一计时权威。
- 完整组卷权重与错题两次不同会话消标不得简化。
- 视觉只能读取 `contracts/design-tokens.json`。
- `tests/` 由 F 独占；B–F 可运行测试，不修改彼此模块。
- 每个任务完成后运行自测、记录实际输出，最后由 Lead 集成。
- M1 采用严格串行实施；子 Agent 并行复核当前阻塞，不把并行作为排期前提。

## Serial Schedule

| 顺序 | 任务 | 预计耗时 | 前置 |
|---:|---|---:|---|
| 1 | M0 签字冻结与基线确认 | 1 小时 | 用户签字 |
| 2 | 运行时、Compose、API 骨架 | 3 小时 | 1 |
| 3 | 契约加载与数据库迁移 | 4 小时 | 2 |
| 4 | Bank 生命周期与隔离 | 4 小时 | 3 |
| 5 | Demo Bank 60 题与校验器 | 8 小时 | 4 |
| 6 | 完整组卷算法 | 6 小时 | 5 |
| 7 | 服务端会话、判分、错题 | 6 小时 | 6 |
| 8 | 单次报告与数据接口 | 5 小时 | 7 |
| 9 | Expo 基础、令牌、离线与计时 | 6 小时 | 8 |
| 10 | App 四页面 | 8 小时 | 9 |
| 11 | 契约、隔离、安全与视觉验收 | 6 小时 | 10 |
| 12 | README、待补齐清单与 M1 证据 | 3 小时 | 11 |

串行总估算：约 60 个开发小时，折合约 8 个标准工作日；实际工期取决于环境安装、真机连接和题库人工审核。

串行只影响 M1 完成时间，不改变验收范围、测试项或质量门槛。

---

### Task 1: 运行时与服务骨架

**Files:**
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `backend/pyproject.toml`
- Create: `apps/mobile/package.json`
- Create: `api/main.py`, `api/deps.py`
- Test: `tests/contracts/test_runtime_contracts.py`

**Interfaces:**
- Consumes: `.nvmrc`, `.python-version`
- Produces: `GET /healthz -> {"status": "ok"}`；容器服务 `postgres`, `redis`, `api`

- [ ] **Step 1: Write the failing contract test**

```python
from pathlib import Path

def test_locked_runtimes_and_compose_services_exist():
    root = Path(__file__).parents[2]
    assert (root / ".nvmrc").read_text().strip() == "24"
    assert (root / ".python-version").read_text().strip() == "3.12"
    compose = (root / "docker-compose.yml").read_text()
    for service in ("postgres:", "redis:", "api:"):
        assert service in compose
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/contracts/test_runtime_contracts.py -v`  
Expected: FAIL because `docker-compose.yml` does not exist.

- [ ] **Step 3: Add runtime files and health endpoint**

`backend/pyproject.toml` must pin Python `>=3.12,<3.13`, FastAPI, Uvicorn, SQLAlchemy, psycopg, redis, pydantic-settings, pytest and httpx. Compose must expose `8000`, mount no production secrets, and use health checks.

```python
# api/main.py
from fastapi import FastAPI

app = FastAPI(title="English Practice API")

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Verify health and compose**

Run: `docker compose config`  
Expected: exit 0 with services rendered.  
Run: `curl http://localhost:8000/healthz`  
Expected: `{"status":"ok"}`

- [ ] **Step 5: Commit**

```bash
git add .env.example docker-compose.yml backend api tests/contracts/test_runtime_contracts.py
git commit -m "feat: add locked local runtime and API skeleton"
```

### Task 2: 契约校验器与配置加载

**Files:**
- Create: `services/practice/config_loader.py`
- Create: `tests/contracts/test_curriculum_contract.py`
- Create: `tests/contracts/test_openapi_contract.py`

**Interfaces:**
- Produces: `load_curriculum() -> Curriculum`；`load_practice_modes() -> PracticeModes`
- Produces: 启动时验证 25 单元、语法 tag 与百分比总和

- [ ] **Step 1: Write the failing tests**

```python
def test_curriculum_has_exactly_25_units(curriculum):
    assert len(curriculum.units) == 25
    assert {
        "必修第一册": 5,
        "必修第二册": 5,
        "必修第三册": 5,
        "选择性必修第一册": 5,
        "选择性必修第二册": 5,
    } == curriculum.unit_counts()

def test_distributions_sum_to_one(curriculum):
    assert abs(sum(curriculum.difficulty_values()) - 1.0) < 1e-9
    assert abs(sum(curriculum.question_book_values()) - 1.0) < 1e-9
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/contracts/test_curriculum_contract.py -v`  
Expected: FAIL because `config_loader` is missing.

- [ ] **Step 3: Implement strict loaders**

Use Pydantic models with `extra="forbid"`. Reject unknown grammar tags, unit counts other than 25, weights outside `[0,1]`, and percentages not summing to 1.

- [ ] **Step 4: Lint OpenAPI and run contract tests**

Run: `npx @redocly/cli lint contracts/openapi.yaml`  
Expected: 0 errors.  
Run: `python -m pytest tests/contracts -v`  
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/practice/config_loader.py tests/contracts
git commit -m "feat: validate curriculum and openapi contracts at startup"
```

### Task 3: Bank 与数据库隔离

**Files:**
- Create: `services/question_pipeline/models.py`
- Create: `services/question_pipeline/repository.py`
- Create: `tests/practice/test_bank_isolation.py`
- Test: `db/migrations/001_initial.sql`

**Interfaces:**
- Produces: `create_bank(name, target_size, difficulty_profile) -> Bank`
- Produces: `activate_bank(bank_id, actor, now) -> Bank`
- Guarantees: `question.bank_id == passage.bank_id == session.bank_id`

- [ ] **Step 1: Write the failing isolation tests**

```python
def test_generation_for_bank_b_does_not_change_bank_a(db, seed_bank_a):
    before = db.questions_snapshot(seed_bank_a.id)
    seed_generated_bank(db, name="Bank B")
    after = db.questions_snapshot(seed_bank_a.id)
    assert after == before

def test_activate_does_not_change_existing_session_bank(db, active_bank, ready_bank):
    session = db.create_session(bank_id=active_bank.id)
    db.activate_bank(ready_bank.id)
    assert db.get_session(session.id).bank_id == active_bank.id
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/practice/test_bank_isolation.py -v`  
Expected: FAIL because repository operations are missing.

- [ ] **Step 3: Implement transaction-safe Bank operations**

Use `SELECT ... FOR UPDATE` for activation. Reject insertion into non-`draft`/`generating` Banks. Never expose update-or-create on `question_banks`.

- [ ] **Step 4: Run integration tests**

Run: `docker compose up -d postgres`  
Run: `python -m pytest tests/practice/test_bank_isolation.py -v`  
Expected: PASS; active bank uniqueness and append rejection are asserted.

- [ ] **Step 5: Commit**

```bash
git add services/question_pipeline tests/practice/test_bank_isolation.py
git commit -m "feat: enforce immutable bank isolation"
```

### Task 4: Demo Bank 与五类校验

**Files:**
- Create: `services/question_pipeline/demo_bank.json`
- Create: `services/question_pipeline/validators.py`
- Create: `services/question_pipeline/seed.py`
- Test: `tests/question_pipeline/test_demo_bank.py`
- Test: `tests/question_pipeline/test_validators.py`

**Interfaces:**
- Produces: `validate_bank(items) -> ValidationReport`
- Produces: `seed_demo_bank(session) -> Bank`
- Consumes: curriculum and vocabulary whitelist

- [ ] **Step 1: Write the failing Demo Bank tests**

```python
def test_demo_bank_has_required_counts(demo_items):
    by_type = Counter(item["type"] for item in demo_items)
    assert by_type == Counter(
        cloze=30, grammar_fill=20, reading=20, gap_fill=10
    )
    assert len({item["passage_group_id"] for item in demo_items}) == 11

@pytest.mark.parametrize("item", load_demo_items())
def test_demo_item_passes_scope(item, curriculum, vocab):
    report = validate_question(item, curriculum, vocab)
    assert report.accepted, report.reasons
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/question_pipeline -v`  
Expected: FAIL because Demo Bank and validator do not exist.

- [ ] **Step 3: Create original Demo content**

Create 11 original passages with 60 questions. Every question has at least three explanation sentences, unique information locus, approved book source and topic. Do not copy exam passages or textbook articles.

- [ ] **Step 4: Implement validators**

Implement Schema, answer/options, word count, vocabulary, grammar, topic, explanation, similarity and 7-option gap-fill checks. Similarity is within the target Bank only.

- [ ] **Step 5: Run validation**

Run: `python -m pytest tests/question_pipeline -v`  
Expected: all 60 questions pass and an injected invalid item fails with a named reason.

- [ ] **Step 6: Commit**

```bash
git add services/question_pipeline tests/question_pipeline
git commit -m "feat: add validated 60-question demo bank"
```

### Task 5: 完整组卷权重与约束

**Files:**
- Create: `services/practice/selection.py`
- Create: `services/practice/paper.py`
- Test: `tests/practice/test_selection_weight.py`
- Test: `tests/practice/test_paper_composition.py`

**Interfaces:**
- Produces: `question_weight(candidate: Candidate, context: SelectionContext) -> float`
- Produces: `compose_paper(student_id, bank_id, mode, now, rng) -> PaperDraft`

- [ ] **Step 1: Write the failing formula tests**

```python
def test_exact_weight_formula():
    c = Candidate(i_err=1, s_kp=5, s_type=1, g_gap=0.25)
    ctx = SelectionContext(r_recent3=1, r_7d=1)
    # 1 + 2 + 1*3 + .5 + .8*.25 - 1.2 - .6
    assert question_weight(c, ctx) == pytest.approx(4.9)

def test_missing_history_has_natural_zero_bonus():
    c = Candidate(i_err=0, s_kp=0, s_type=0, g_gap=0)
    assert question_weight(c, SelectionContext(0, 0)) == 1.0
```

- [ ] **Step 2: Write failing composition tests**

```python
@pytest.mark.parametrize(
    ("minutes", "counts"),
    [(30, {29, 30}), (60, {42})],
)
def test_paper_counts(minutes, counts, seeded_student):
    paper = compose_paper(seeded_student, seeded_student.active_bank_id, str(minutes))
    assert len(paper.items) in counts
    assert {item.bank_id for item in paper.items} == {seeded_student.active_bank_id}
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `python -m pytest tests/practice/test_selection_weight.py tests/practice/test_paper_composition.py -v`  
Expected: FAIL because `question_weight` and `compose_paper` are missing.

- [ ] **Step 4: Implement weighted sampling and constraints**

Use seeded `random.Random` in tests. Use weighted sampling without replacement inside each type. Apply paper difficulty, book distribution, error-pool, knowledge repetition, topic and Bank constraints.

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/practice/test_selection_weight.py tests/practice/test_paper_composition.py -v`  
Expected: PASS for 30- and 60-minute modes; no item has wrong `bank_id`.

- [ ] **Step 6: Commit**

```bash
git add services/practice tests/practice/test_selection_weight.py tests/practice/test_paper_composition.py
git commit -m "feat: implement weighted adaptive paper composition"
```

### Task 6: 服务端会话、判分与错题生命周期

**Files:**
- Create: `services/practice/sessions.py`
- Create: `services/practice/grading.py`
- Create: `services/practice/error_tags.py`
- Test: `tests/practice/test_sessions.py`
- Test: `tests/practice/test_grading.py`
- Test: `tests/practice/test_error_tags.py`

**Interfaces:**
- Produces: `start_session(student_id, duration, now) -> Session`
- Produces: `submit_session(student_id, session_id, now) -> SessionResult`
- Produces: `apply_answer_outcome(tag, correct, session_id) -> ErrorTag`

- [ ] **Step 1: Write failing deadline and leakage tests**

```python
def test_session_response_has_no_answer_fields(session_client):
    payload = session_client.get(f"/practice/{session_client.session_id}").json()
    json_text = json.dumps(payload)
    assert '"answer"' not in json_text
    assert '"explanation"' not in json_text

def test_expired_session_autosubmits(clock, student, active_bank):
    session = start_session(student.id, 30, clock.now)
    clock.advance(minutes=31)
    result = submit_session(student.id, session.id, clock.now)
    assert result.status == "expired"
```

- [ ] **Step 2: Write failing error lifecycle tests**

```python
def test_two_successes_in_different_sessions_master_tag(tag):
    apply_answer_outcome(tag, False, "s0")
    apply_answer_outcome(tag, True, "s1")
    apply_answer_outcome(tag, True, "s1")
    assert tag.status == "active"
    apply_answer_outcome(tag, True, "s2")
    assert tag.status == "mastered"
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `python -m pytest tests/practice/test_sessions.py tests/practice/test_grading.py tests/practice/test_error_tags.py -v`  
Expected: FAIL because session and grading services are missing.

- [ ] **Step 4: Implement transitions and transactions**

Set deadline from server time. Submit is idempotent. Grade in session Bank only. Update `error_tag_successes` only when the session ID is new. Update EWMA on the reporting service transaction boundary.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/practice/test_sessions.py tests/practice/test_grading.py tests/practice/test_error_tags.py -v`  
Expected: PASS, including same-session duplicate and re-activation after mastered.

- [ ] **Step 6: Commit**

```bash
git add services/practice tests/practice/test_sessions.py tests/practice/test_grading.py tests/practice/test_error_tags.py
git commit -m "feat: add server-timed grading and error lifecycle"
```

### Task 7: 单次报告与跨库掌握度

**Files:**
- Create: `services/reporting/mastery.py`
- Create: `services/reporting/single_report.py`
- Create: `services/reporting/stage_report.py`
- Test: `tests/reporting/test_mastery.py`
- Test: `tests/reporting/test_single_report.py`
- Test: `tests/reporting/test_stage_report_contract.py`

**Interfaces:**
- Produces: `update_ewma(old, score) -> float`
- Produces: `build_single_report(session_result) -> Report`
- Produces: `build_stage_report(student_id, range) -> StageReport`

- [ ] **Step 1: Write failing report tests**

```python
def test_ewma_alpha_point_three():
    assert update_ewma(0.5, 1.0) == pytest.approx(0.65)

def test_report_has_bank_name_and_three_weak_points(report):
    assert report["bank_name"] == "Demo Bank"
    assert len(report["weak_points"]) <= 3
    assert all(item["knowledge_point"] for item in report["suggestions"])
```

- [ ] **Step 2: Write failing cross-bank stage contract**

```python
def test_stage_report_requires_cross_bank_notice(reports_from_two_banks):
    report = build_stage_report(reports_from_two_banks)
    assert "跨 2 份题库" in report["cross_bank_notice"]
    assert "原题错题加权失效" in report["cross_bank_notice"]
    assert "知识点缺口跨库继承" in report["cross_bank_notice"]
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `python -m pytest tests/reporting -v`  
Expected: FAIL because reporting services are missing.

- [ ] **Step 4: Implement reporting**

Compute type accuracy, knowledge levels, weak Top3, concrete suggestions, EWMA, last-5 slope and stddev. Stage reports must expose `cross_bank_notice`.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/reporting -v`  
Expected: PASS and JSON validates against `contracts/schemas/report.json`.

- [ ] **Step 6: Commit**

```bash
git add services/reporting tests/reporting
git commit -m "feat: generate single and cross-bank stage reports"
```

### Task 8: FastAPI 学生接口与安全接线

**Files:**
- Create: `api/routes/practice.py`
- Create: `api/routes/reports.py`
- Create: `api/routes/student_data.py`
- Test: `tests/api/test_student_api.py`
- Test: `tests/api/test_answer_secrecy.py`

**Interfaces:**
- Consumes: practice and reporting services
- Produces: OpenAPI paths for start/get/answer/submit/report/summary/error-tags/delete

- [ ] **Step 1: Write failing API tests**

```python
def test_student_cannot_read_another_students_session(client, two_students):
    response = client.get(
        f"/api/v1/practice/{two_students.alice_session}",
        headers={"X-Student-Id": str(two_students.bob)},
    )
    assert response.status_code == 404

def test_delete_student_data_removes_only_that_student(client, two_students):
    client.delete("/api/v1/student-data", headers={"X-Student-Id": str(two_students.alice)})
    assert count_student_rows(two_students.alice) == 0
    assert count_student_rows(two_students.bob) > 0
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m pytest tests/api -v`  
Expected: FAIL because routes do not exist.

- [ ] **Step 3: Implement routes with no-answer DTOs**

Use dependency injection for student ID and repositories. Serialize `SessionResponse` explicitly; never `model_dump()` the database question model.

- [ ] **Step 4: Run API tests**

Run: `python -m pytest tests/api -v`  
Expected: PASS; unsubmitted responses, logs and local cache fixture contain no `answer` or `explanation`.

- [ ] **Step 5: Commit**

```bash
git add api tests/api
git commit -m "feat: expose secure student practice API"
```

### Task 9: Expo 基础、设计令牌与离线草稿

**Files:**
- Create: `apps/mobile/src/theme/tokens.ts`
- Create: `apps/mobile/src/storage/deviceIdentity.ts`
- Create: `apps/mobile/src/storage/sessionDraft.ts`
- Create: `apps/mobile/src/api/client.ts`
- Create: `apps/mobile/src/time/serverClock.ts`
- Test: `apps/mobile/src/**/__tests__/*.test.ts`

**Interfaces:**
- Produces: `getOrCreateStudentId() -> Promise<string>`
- Produces: `saveDraft(sessionId, questionId, answer) -> Promise<void>`
- Produces: `reconcileDeadline(deadline, serverTime) -> remainingSeconds`

- [ ] **Step 1: Write failing token and storage tests**

```typescript
test("tokens load from design-tokens source", () => {
  expect(tokens.color.pageBackground).toBe("#FFFFFF");
  expect(tokens.radius.large).toBe(14);
});

test("draft never contains answer or explanation keys", async () => {
  await saveDraft("session", "question", "B");
  const raw = await storage.get("session-draft-session");
  expect(raw).not.toContain('"answer"');
  expect(raw).not.toContain('"explanation"');
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `cd apps/mobile && npm test -- --runInBand`  
Expected: FAIL because token, storage and time modules do not exist.

- [ ] **Step 3: Add Expo SDK 58 TypeScript scaffold**

Use system fonts only. Generate an importable token object from `contracts/design-tokens.json` during build; do not copy raw hex values into screens.

- [ ] **Step 4: Implement identity, draft storage and server clock**

Validate UUID v4. Store session draft under a session-specific key. Recalculate remaining time from `deadline`, `server_time` and current monotonic elapsed time.

- [ ] **Step 5: Run unit tests and typecheck**

Run: `npm test -- --runInBand`  
Run: `npx tsc --noEmit`  
Expected: PASS and 0 TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add apps/mobile
git commit -m "feat: add token-driven mobile foundation and offline drafts"
```

### Task 10: 四页面流程

**Files:**
- Create: `apps/mobile/app/_layout.tsx`
- Create: `apps/mobile/app/index.tsx`
- Create: `apps/mobile/app/practice/[sessionId].tsx`
- Create: `apps/mobile/app/report/[sessionId].tsx`
- Create: `apps/mobile/app/analysis/[sessionId].tsx`
- Test: `apps/mobile/src/screens/__tests__/flow.test.tsx`

**Interfaces:**
- Consumes: API client, tokens, draft and server clock
- Produces: Home → Practice → Report → Analysis navigation

- [ ] **Step 1: Write failing component tests**

```tsx
test("home shows active bank name and both durations", async () => {
  render(<HomeScreen data={{bankName: "Demo Bank"}} />);
  expect(screen.getByText(/当前题库：Demo Bank/)).toBeVisible();
  expect(screen.getByText("30 分钟")).toBeVisible();
  expect(screen.getByText("60 分钟")).toBeVisible();
});

test("submitting requires confirmation", async () => {
  render(<PracticeScreen session={fixture} />);
  fireEvent.press(screen.getByText("交卷"));
  expect(screen.getByText("确认交卷？")).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `npm test -- --runInBand apps/mobile/src/screens/__tests__/flow.test.tsx`  
Expected: FAIL because screens do not exist.

- [ ] **Step 3: Build the four screens**

Practice screen includes serif passage, sans-serif questions, answer card, progress, countdown and scroll-to-hide passage. Report shows all required metrics. Analysis shows per-question answer, explanation, tags and book source.

- [ ] **Step 4: Run component tests, typecheck and lint**

Run: `npm test -- --runInBand`  
Run: `npx tsc --noEmit`  
Run: `npm run lint`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/app apps/mobile/src/screens
git commit -m "feat: implement M1 student practice flow"
```

### Task 11: 契约、隔离、安全与视觉自动验收

**Files:**
- Create: `tests/contracts/test_openapi_runtime.py`
- Create: `tests/practice/test_bank_switch_semantics.py`
- Create: `tests/security/test_answer_secrecy.py`
- Create: `qa/check_tokens.py`
- Create: `qa/check_no_hardcoded_styles.py`
- Create: `qa/run_acceptance.ps1`
- Output: `qa/evidence/m1/*`

**Interfaces:**
- Consumes: running API, Expo web or connected device
- Produces: machine-readable and screenshot acceptance evidence

- [ ] **Step 1: Write failing acceptance checks**

```python
def test_no_answer_fields_before_submit(api, session):
    body = api.get(f"/practice/{session.id}").text
    assert '"answer"' not in body
    assert '"explanation"' not in body

def test_bank_switch_preserves_existing_session(api, two_banks):
    session = api.start(active_bank=two_banks.a)
    api.activate(two_banks.b)
    assert api.get_session(session.id).bank_id == two_banks.a
```

- [ ] **Step 2: Run checks and verify they fail before final wiring**

Run: `python -m pytest tests/contracts tests/practice/test_bank_switch_semantics.py tests/security -v`  
Expected: any missing wiring reports a concrete failing assertion.

- [ ] **Step 3: Implement evidence scripts**

`check_tokens.py` parses the tokens file and screens. `check_no_hardcoded_styles.py` exits nonzero on hex colors, `fontSize` numeric literals or raw spacing literals in screen code, excluding the token adapter and tests.

- [ ] **Step 4: Capture four screenshots**

Capture Home, Practice, Report and Analysis at a consistent device viewport. Store under `qa/evidence/m1/screenshots/`. Record device, OS, Expo SDK, viewport and timestamp.

- [ ] **Step 5: Run full suite**

Run: `docker compose up -d`  
Run: `python -m pytest tests -v`  
Run: `npm test -- --runInBand`  
Run: `python qa/check_tokens.py`  
Run: `python qa/check_no_hardcoded_styles.py`  
Expected: all pass; screenshot comparison has 0 deviations.

- [ ] **Step 6: Commit**

```bash
git add tests qa
git commit -m "test: add M1 contract isolation security and visual evidence"
```

### Task 12: M1 文档与验收清单

**Files:**
- Modify: `README.md`
- Create: `docs/milestones/M1-acceptance.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: all task evidence
- Produces: five-step startup, demo path and V11 items 1–11 evidence table

- [ ] **Step 1: Write the acceptance document with real evidence**

Each V11 item 1–11 gets command, exit code, output summary, artifact path and N/A reason if applicable. Items 10 and 11 include screenshots and grep output.

- [ ] **Step 2: Update README**

Document Node 24, Python 3.12, `docker compose up`, `npx expo start`, physical device steps, `--tunnel` option and demo flow in no more than five startup steps.

- [ ] **Step 3: Run documentation checks**

Run: `rg -n "TODO|TBD|待补" README.md docs/milestones/M1-acceptance.md`  
Expected: no unfinished placeholders in milestone evidence; deferred items remain only in `docs/待补齐清单.md`.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/milestones/M1-acceptance.md CHANGELOG.md
git commit -m "docs: publish reproducible M1 acceptance evidence"
```

## Handoff

M0 完成后由系统所有者核对并签字冻结。当前 3 个只读子 Agent 冒烟复核结果为 0/3，多 Agent 并行已标记阻塞，M1 按上述顺序严格串行执行。Git 基线、运行版本锁定和已有契约必须保持完整。
