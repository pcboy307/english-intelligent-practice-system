# Windows 自包含安装器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个免管理员、免外部运行时的 Windows x64 安装器。

**Architecture:** 便携 Python 启动现有 FastAPI；便携 PostgreSQL 首次初始化；本地 SPA 服务提供 Expo Web；Inno Setup 负责按用户安装和快捷方式。

**Tech Stack:** Expo Web, FastAPI, PostgreSQL 16, portable Python 3.12, PowerShell, Inno Setup.

**Spec:** `docs/superpowers/specs/2026-11-13-windows-installer-design.md`

## Global Constraints

- Target Windows 10/11 x64.
- Per-user install with no UAC.
- Ports: Web 8081, API 8000, PostgreSQL 15432.
- Database name: `english_practice`.
- Target machine must not require Node, Python, Docker, or PostgreSQL.
- User data must survive upgrades.
- No commercial code-signing certificate is available.

---

### Task 1: Desktop Runtime

**Files:**
- Create: `desktop/bootstrap.py`
- Create: `desktop/launcher.pyw`
- Create: `desktop/static_server.py`
- Create: `desktop/stop.pyw`
- Test: `tests/desktop/test_desktop_runtime.py`

**Interfaces:**
- Produces: `runtime_paths()`, `ensure_database()`, `start_services()`, `stop_services()`.

- [ ] Write tests for data paths, migration order, fixed DB URL, idempotent init decisions.
- [ ] Run tests and verify failure before implementation.
- [ ] Implement minimal runtime functions.
- [ ] Run tests until pass.
- [ ] Commit runtime layer.

### Task 2: Static Web and API Process

**Files:**
- Modify: `desktop/launcher.pyw`
- Modify: `desktop/static_server.py`

**Interfaces:**
- Consumes: Task 1 path and process helpers.
- Produces: local endpoints on 8081 and 8000.

- [ ] Start FastAPI with bundled Python and no console window.
- [ ] Serve Expo files with `index.html` fallback.
- [ ] Wait for both health endpoints before opening browser.
- [ ] Stop both processes by PID without killing unrelated processes.
- [ ] Verify repeated launcher calls only open the browser.

### Task 3: Build Staging

**Files:**
- Create: `scripts/build-windows-installer.ps1`
- Create: `docs/windows-installer-build.md`

**Interfaces:**
- Consumes: desktop runtime files and current repository runtime.
- Produces: `dist/windows/package/`.

- [ ] Typecheck and export Expo Web.
- [ ] Copy backend/config/contracts/migrations/desktop.
- [ ] Copy portable Python and install exact Python dependencies.
- [ ] Copy PostgreSQL `bin`, `lib`, `share` and licenses.
- [ ] Export current active Bank seed.
- [ ] Fail clearly if any required runtime path is missing.

### Task 4: Inno Setup Installer

**Files:**
- Create: `installer/gaoer-english-practice.iss`
- Modify: `scripts/build-windows-installer.ps1`

**Interfaces:**
- Consumes: staged package.
- Produces: `dist/windows/GaoerEnglishPractice-Setup.exe`.

- [ ] Configure per-user install, shortcuts and uninstall.
- [ ] Stop services before uninstall.
- [ ] Preserve `%LOCALAPPDATA%\GaoerEnglishPractice\data`.
- [ ] Build with Inno Setup and compute SHA-256.

### Task 5: End-to-End Acceptance

**Files:**
- Create: `docs/milestones/windows-installer-acceptance.md`

**Interfaces:**
- Consumes: installer or staged package.
- Produces: reproducible acceptance evidence.

- [ ] Run staged launcher against clean temporary data directory.
- [ ] Confirm active Bank is 72 passages / 500 questions.
- [ ] Complete browser practice and report.
- [ ] Stop and restart; confirm report still exists.
- [ ] Install silently into a temporary per-user target.
- [ ] Record tests, size, checksum, limitations and second-PC-only checks.
