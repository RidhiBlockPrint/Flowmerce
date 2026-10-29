# Flowmerce project rules

These are the permanent engineering rules for Flowmerce. They apply to every task, by every developer or assistant. Where a request conflicts with them, stop, name the conflict and ask the owner. Do not change these rules silently.

Priority order: (1) the owner's explicit instructions and approvals, (2) correctness and security, (3) clear architecture and maintainability, (4) accurate documentation, (5) reliable testing, (6) development speed.

The owner directs the project and makes all business decisions. The developer (or assistant) is responsible for explaining technical work clearly enough that the owner can supervise it.

Related documents: [README](README.md) · [Roadmap](docs/development/roadmap.md) · [Coding standards](docs/development/coding-standards.md) · [Folder structure](docs/architecture/folder-structure.md) · [File registry](docs/FILE_REGISTRY.md) · [Decisions](docs/decisions/).

## 1. Languages

1. Python is the primary language (ADR 0001).
2. Approved exceptions are recorded in [ADR 0002](docs/decisions/0002-approved-language-exceptions.md) and are limited to:
   - **Python is the backend language.** The frontend is **Next.js + React in JavaScript/JSX only** (owner decision, [ADR 0006](docs/decisions/0006-nextjs-javascript-frontend.md)), in `frontend/`. **TypeScript is not allowed in the frontend**: no `.ts`/`.tsx` files, no `tsconfig`, no `typescript` or `@types/*` packages, no type annotations. Vite is no longer used. The frontend calls the Python API through `/api/...` and holds no credentials, backend, integration or business logic. It does not approve any other UI framework or language.
   - Plain `.sql` files for database schema only, under `db/`.
3. Any other language (including shell or batch scripts beyond what already exists) needs an explanation of why it is needed, what it provides and whether a Python alternative exists, **and the owner's explicit approval before any code is written**. A framework or tutorial recommending a language is not approval.
4. Markdown and ordinary configuration files are always allowed. A tool whose configuration contains executable code in another language needs approval first.

## 2. Decisions and approvals

Ask the owner before:
- introducing a language, framework, database, queue, hosting platform or other significant technology;
- making an architecture decision that is not already recorded (open questions stay open until the owner decides; see the roadmap);
- implementing a business feature or module the owner has not defined or prioritised. Never invent requirements;
- deleting, moving, overwriting, migrating, publishing, deploying, pushing to a remote, or changing credentials or live data;
- committing, unless the owner has asked for it.

Significant decisions are recorded as ADRs in `docs/decisions/` using `0000-template.md` (decision, rationale, alternatives, advantages, disadvantages, consequences, status). Do not write ADRs for trivial choices.

## 3. Workflow for every change

1. **Inspect** the relevant files, dependencies, current behaviour, documentation and Git status. Prefer read-only inspection first.
2. **Locate** the correct module and file before writing code.
3. **Explain** the plan briefly: objective, business value, current state, approach, files affected, risks and dependencies, and what you need from the owner. Keep it beginner-friendly without omitting important engineering detail.
4. **Check language and approval constraints** (sections 1 and 2).
5. **Implement** focused, modular changes. Preserve existing behaviour unless the task requires otherwise.
6. **Test** with the available tests and checks.
7. **Document** in the same change (section 6).
8. **Review** imports, dependencies, configuration, security, regressions and naming.
9. **Report** using the completion report (section 9).

Small changes get proportionate process. Do not redesign unrelated components.

## 4. Code and structure

- **Folders:** every source file has one clear home by purpose, module and responsibility (see [folder structure](docs/architecture/folder-structure.md)). Application code in `src/flowmerce/`, tests in `tests/`, docs in `docs/`, scripts in `scripts/`, schema SQL in `db/`, UI in `frontend/`. Create a folder only when it holds real code. No scattered files, unexplained scripts, duplicate implementations, `misc`/`utils2` names or oversized catch-all files.
- **Modularity:** one responsibility per file; separate business logic, configuration, external integrations and presentation. Modules do not import each other's internals. No empty placeholder implementations, unneeded abstraction layers or frameworks that solve no identified problem.
- **Readability:** prefer plain, understandable Python.
- **Types:** annotate public functions and data structures; `mypy --strict` must pass for new code.
- **Docstrings and comments:** every module, public class and public function has a docstring; explain business rules and non-obvious logic, not the obvious.
- **Errors:** raise specific exceptions with actionable messages; no bare `except:`, no silent swallowing; catch broad `Exception` only at process boundaries and log it.
- **Logging:** use `logging.getLogger(__name__)`; consistent format; never log secrets, tokens, passwords or customer personal data.
- **Configuration and secrets:** environment-based; no secrets in source code; `.env` is git-ignored and `.env.example` is kept current and safe.
- **Dependencies:** avoid unnecessary packages; add one only with a stated reason recorded in `docs/development/setup.md` and declared in `pyproject.toml`.
- **Testing:** new behaviour and bug fixes ship with tests (unit tests for isolated logic, integration tests for component interaction). Tests must not need the network or real credentials. Legacy-code lint and type exclusions are tracked in the roadmap and removed as files are cleaned up; new code must meet the standards in full.
- Details and tool settings: [coding standards](docs/development/coding-standards.md).

## 5. Preservation

- Do not discard or overwrite existing code, Git history or unrelated working-tree changes. Look at a target before deleting or overwriting it.
- Do not rewrite shared Git history or force-push without the owner's explicit instruction.
- Live data and secrets (`.env`, `data/`, `backups/`) are never committed or printed in logs, chat or documents.

## 6. Documentation is part of the change

Whenever a file is created, modified, moved or removed, update in the same task, as applicable:
- `docs/FILE_REGISTRY.md` (path, responsibility, main components, dependencies, dependents, tests, status, notes);
- `docs/architecture/folder-structure.md` when structure changes;
- `docs/development/setup.md` for setup, dependency or configuration changes;
- `docs/architecture/system-overview.md` for architecture changes;
- `docs/decisions/` for significant decisions;
- `docs/development/roadmap.md` so status matches the repository;
- `CHANGELOG.md` (dated; Added, Changed, Fixed, Removed, Architecture).

Documentation must describe what exists. Never document functionality that does not exist, and mark planned or unverified work as such.

## 7. Evidence-based reporting

- Never say code, tests, integrations or features work unless evidence supports it. State what was actually run, the result, and what was **not** run or verified.
- Never claim a test passed if it was not executed successfully. If checks from an earlier session were not re-run, say so.
- For a bug: record the observed problem, the root cause where established, the fix and a regression test where appropriate. Label a hypothesis as a hypothesis; do not present it as a proven cause.
- Errors are handled by: identify the exact error and context, explain the likely cause in plain language, investigate before touching unrelated files, apply a targeted fix, verify it, document it.

## 8. Guided development (owner support)

- Work task by task; do not try to build the whole ERP in one prompt. The general sequence is: workspace inspection, engineering rules and documentation, requirements and architecture, initial release scope and priorities, database and data-model design (owner approves the approach), application foundation, individual approved business modules, integrations, full testing, deployment preparation and operating documentation. Adapt it to real requirements and use the simplest architecture that fits.
- Explain each significant task before running it. When the owner needs to act, give the exact prompt, working directory and commands, with what each does, the expected output, how to verify, and what to share for review. Do not assume the owner knows how to run commands or read errors.
- Ask focused questions only where clarification is essential, and do not re-ask what the owner already answered.
- Keep the [roadmap](docs/development/roadmap.md) current and recommend only the next logical task.

## 9. Completion report

At the end of each meaningful task report: (1) what was completed, (2) files created, modified or deleted, (3) what each important file is responsible for, (4) tests and checks actually performed, (5) whether they passed or failed, (6) known limitations and unresolved issues, (7) the next recommended task and why.

## 10. Handover

A new developer must be able to, without asking the original developer: find a feature quickly, trace dependencies, understand why design choices were made, know where a new feature belongs, reproduce the environment, run tests and investigate failures, review changes, and tell completed functionality from planned work. Nothing important may live only in conversation history or in one person's knowledge.

## 11. Phases and file-modification approval

Set by the owner on 2026-10-29. This section controls when files may be changed.

**Initial setup phase (ended).** During the engineering-foundation phase the developer could make in-scope setup changes without per-change approval: folder structure, `PROJECT_RULES.md`, roadmap, README, engineering documentation, tooling configuration where software was already available, and verified removal of unused or obsolete files. That permission never covered installing software, adding a language, migrating databases, altering live services, or building business features, and it was always subject to preserving the SEO & Blog module, the frontend, Git history, user data and credentials.

**Transition.** The setup phase ended when work began on the product interface (the shared application shell and main dashboard) or on any business module, whichever came first. That was the Phase 2 dashboard task.

**Product development phase (current).** No file may be created, edited, moved, renamed or deleted without the owner's explicit approval of the proposed changes. For every task:

1. Inspect the repository, relevant files, dependencies and Git status.
2. Explain the task, the proposed implementation, the benefits and the risks.
3. List the files to create, modify, move, rename or delete, with a reason for each.
4. List cleanup opportunities separately from the requested work.
5. Wait for the owner's explicit approval.
6. Implement only what was approved, then run the relevant checks.
7. If more files or changes turn out to be needed, stop and ask again before making them.
8. Report the actual changes, deleted files, tests run and remaining issues.

Read-only inspection and analysis need no approval. Silence, a request for analysis or a request for a plan is not permission to modify files.

**Scope of approval.** Approval covers only the specific task and changes presented. It does not authorise, for example: rewriting the SEO & Blog module, changing the database architecture, installing Node.js or other packages, deleting files outside an approved cleanup, building other business modules, connecting to live accounts, or running platform-changing actions. If the work cannot be done within the approved scope, say what extra authorisation is needed.

**Cleanup.** Unused files, redundant dependencies and obsolete code may be identified during inspection but are removed or changed only with approval. Never remove something merely because it appears unused: first check imports, dynamic loading, routes, configuration, tests, scripts, integrations, documentation, build requirements and approved future plans. After approved cleanup, run the relevant checks and document meaningful deletions.

**Permanent.** The owner's authority applies at every stage. Setup permission is never extended into product development, and approval for one task is never blanket authorisation for later ones.
