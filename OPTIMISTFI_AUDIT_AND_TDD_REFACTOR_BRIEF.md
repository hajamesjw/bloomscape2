# OptimistFi: Codebase Audit, Test Strategy, and TDD Refactoring Plan

## A complete briefing for Claude Code

---

# PART A: READ THIS FIRST (for the human running this)

You are not expected to be a developer. This document is written so that Claude does the work and you only have to start it, let it run, and read the results. This section tells you exactly what to do. Everything after Part A is written for Claude.

## A.1 What this document does

Claude will study every part of the optimistfi.com codebase (website, backend logic, database) and produce a set of reports in a new folder called `docs/refactor/`. The reports will:

1. Describe exactly what is in the codebase today.
2. List every structural problem, with the exact file and line, and explain how each one causes slow edits, high token cost, edits that do not land as described, or regressions.
3. Describe the existing test coverage and where the gaps are.
4. Design the target architecture: how the code should be organized so that each piece can be edited, tested, and debugged in isolation.
5. Design a full test suite that will catch regressions automatically.
6. Produce a numbered, step-by-step refactoring plan where every step is small, writes its tests first, and can be executed by Claude in a later session with a single instruction from you.
7. Produce draft "harness" files (a CLAUDE.md, skills, scripts, lint rules, CI config) that make Claude faster and more accurate on this codebase going forward.

During this run Claude will NOT change any application code. It will only read, analyze, and write reports into `docs/refactor/`. The actual refactoring happens later, one step at a time, using the plan.

## A.2 How to run it

1. Put this file in the root folder of the optimistfi repository (the same folder that contains `package.json` or the equivalent). Name it `OPTIMISTFI_AUDIT_AND_TDD_REFACTOR_BRIEF.md`.
2. Open Claude Code in that folder. Use the most capable model available to you. If there is an "effort" or "thinking" setting, set it to the maximum.
3. Make sure Claude has permission to read files and run read-only shell commands (listing files, counting lines, running the existing test suite, running the linter). If Claude Code asks permission for these, approve them. If it asks to install something small like a code-counting tool, approve it. If it asks to modify any file outside `docs/refactor/`, deny it and tell it to re-read Part B.3.
4. Paste this exact message:

```
Read the file OPTIMISTFI_AUDIT_AND_TDD_REFACTOR_BRIEF.md in full. Follow Part B onward exactly, phase by phase, in order. Do not skip phases, do not summarize instead of doing the work, and do not change any application code. Write all outputs to docs/refactor/ as specified. Keep docs/refactor/PROGRESS.md updated after every phase so you can resume if interrupted. Begin with Phase 0.
```

5. Let it run. This is designed to run for a long time (hours). If Claude stops and asks you a question it cannot answer itself, the answer is almost always "Use your best judgment, document the assumption in the report, and continue."
6. If the session ends, runs out of context, or you come back and it has stopped, open a new Claude Code session in the same folder and paste:

```
Read OPTIMISTFI_AUDIT_AND_TDD_REFACTOR_BRIEF.md and docs/refactor/PROGRESS.md. Resume from the first incomplete phase. Do not redo completed phases; read their output files instead.
```

7. When it finishes, read `docs/refactor/README.md` first. It is the executive summary written for you.

## A.3 What to do after it finishes

The file `docs/refactor/05-refactor-plan.md` contains numbered steps. To execute them, open Claude Code and paste (replace N with the step number, starting at 1):

```
Read docs/refactor/05-refactor-plan.md and docs/refactor/06-execution-protocol.md. Execute Step N exactly as written, following the TDD protocol. Do not start Step N+1. When done, update docs/refactor/PROGRESS.md and show me the test results and a summary of what changed.
```

Do one step at a time. Each step is designed to leave the site working. If a step fails, Claude is instructed to revert and explain, not to push forward.

## A.4 Plain-language glossary

- **Harness**: the small set of files that tell Claude how this codebase works and how to work on it (CLAUDE.md, skills, scripts). "Thin harness" means this layer is short and points to the right places instead of containing everything.
- **Skill**: a reusable, written procedure Claude follows for a recurring task, such as "add a new page" or "add a database field." Stored in `.claude/skills/`. "Fat skills" means the detailed know-how lives here, one skill per task, so Claude loads only what the current task needs.
- **Module / feature slice**: a self-contained folder that owns one feature end to end (its UI, its logic, its data access, its tests). Editing one does not require reading the others.
- **Regression**: something that used to work and now does not because of an unrelated change.
- **TDD (Test-Driven Development)**: write a test that fails because the feature or fix does not exist yet, then write the smallest code that makes it pass, then clean up. Every change is proven by a test before it is written.
- **Characterization test**: a test that records what the code does today, right or wrong, so a refactor can prove it did not change behavior.
- **Strangler fig**: a refactoring approach where new, clean modules are built alongside old code and traffic is moved over piece by piece, so the site never breaks.
- **CI (Continuous Integration)**: an automated system that runs all tests and checks every time code is pushed.

---

# PART B: INSTRUCTIONS FOR CLAUDE

## B.1 Your role and mission

You are a principal-level software architect and test engineer conducting a full structural audit of the optimistfi.com codebase and producing an executable, test-driven refactoring plan.

The person who owns this codebase is not a developer. They build and maintain it entirely through you. Your output will be executed by future instances of you, one step at a time, with the human only pasting a start command. Therefore:

- Every finding must be precise enough that a future Claude session can go directly to the file and line.
- Every recommendation must be an exact action, not advice. "Consider extracting the validation" is unacceptable. "Create `src/modules/accounts/validation.ts` exporting `validateAccountInput(input: unknown): Result<AccountInput, ValidationError>`; move the logic currently at `src/pages/api/accounts.ts:41-88` into it; replace the inline code with a call" is acceptable.
- Every refactoring step must list the tests to write first, by name, with the assertions they make.
- Nothing may be left as "TBD," "to be determined," "as needed," or "etc." If you do not know, investigate until you do, or mark it `UNVERIFIED` with the specific reason and the specific command or check that would resolve it.

## B.2 The problem you are solving

The owner reports four symptoms when making changes through Claude:

1. **Small edits take a long time.** Claude has to read many files to understand where a change belongs and what it will affect.
2. **Token cost is very high.** Same cause: too much context must be loaded for each change because responsibilities are spread out, duplicated, or entangled.
3. **Edits often do not land as described.** The change gets made in one place but the same logic exists elsewhere, or the change breaks an implicit assumption, or the structure is ambiguous enough that Claude picks the wrong location.
4. **Regressions.** Changes break unrelated things, and checking for that manually is slow and incomplete because there is no automated test suite that proves the site still works.

The owner's hypothesis, which you should test rather than assume, is that the codebase lacks a **thin harness, fat skills** architecture with **isolated modules**:

- **Thin harness**: a short root `CLAUDE.md` and a small, stable application shell (routing, dependency wiring, app bootstrap) that contains almost no business logic and rarely changes.
- **Fat skills**: the detailed procedural knowledge for each recurring task (add a page, add an API route, add a DB table, add a validation rule, change a price calculation) lives in dedicated skill files that Claude loads only when doing that task, so each task costs only the context it needs.
- **Isolated modules**: each feature owns its UI, logic, data access, types, and tests in one folder with an explicit public interface. Editing one module requires reading only that module and its interface, not the whole app. Each module can be tested alone.
- **Strong automated tests**: a fast, comprehensive suite that runs on every change so regressions are caught by machines in seconds instead of by humans in hours.

Your job is to determine, with evidence, how far the codebase is from this, and to produce the exact plan to get there without breaking the site.

## B.3 Non-negotiable operating rules

1. **Read-only toward application code.** During this entire brief (Phases 0 through 7) you may create and modify files ONLY inside `docs/refactor/`. You may not modify, move, delete, or format any other file. You may not run commands that change the database, deploy anything, or alter git history. You may run the existing test suite, linter, type checker, and build in their normal read-only modes. If a command would write anywhere other than a temp directory or `docs/refactor/`, do not run it.
2. **Evidence, not impression.** Every claim about the code cites `path/to/file.ext:startLine-endLine`. Every quantitative claim (file counts, line counts, duplication counts, dependency counts) comes from a command you ran, and you record the command.
3. **Exhaustive, not representative.** Do not list "examples of" a problem. List every instance you can find. If a category has 40 instances, the table has 40 rows. Use subagents or systematic searches to cover the whole tree. If a list would exceed 200 rows, put the full list in an appendix file and summarize counts in the main report.
4. **Checkpoint constantly.** After completing each phase, and at least every 30 minutes of work within a phase, update `docs/refactor/PROGRESS.md` with what is done, what file it is in, and what is next. Write report files incrementally as you go rather than holding everything in memory. Assume your context may be reset at any moment.
5. **Do not ask the human to make technical decisions.** If a decision is needed, make it, state it as a decision with reasoning in the relevant report, and continue. The only acceptable questions to the human are ones about business intent that cannot be inferred from code (for example, "Is the legacy `v1_users` table still used by anything outside this repo?"). Even then, write down your best assumption, proceed on it, and list the question in `docs/refactor/OPEN-QUESTIONS.md`.
6. **Adapt to what you find.** This brief uses examples from common web stacks. If the actual stack differs, translate every recommendation to the real stack. Never recommend a tool or pattern that does not fit the actual languages, frameworks, and hosting in use.
7. **Protect secrets.** If you find credentials, API keys, or tokens in the code or config, record the file path and line in the findings as a CRITICAL security finding, but never copy the secret value into any report.
8. **Finance-grade caution.** The domain name suggests a financial product. Treat anything touching money, balances, transactions, pricing, interest, fees, payment providers, user identity, or authorization as highest-risk. These areas get the strictest test requirements and the most conservative refactoring steps.

## B.4 Output files you must produce

All inside `docs/refactor/`:

| File | Produced in | Purpose |
|---|---|---|
| `PROGRESS.md` | Continuously | Checkpoint log for resumption |
| `OPEN-QUESTIONS.md` | Continuously | Business questions only the human can answer, each with your working assumption |
| `00-inventory.md` | Phase 0 | Complete factual inventory of the codebase |
| `01-findings.md` | Phase 1 | Every structural, quality, security, and performance finding with evidence |
| `01-findings-appendix-*.md` | Phase 1 | Long lists (duplication instances, oversized files, etc.) |
| `02-test-coverage-audit.md` | Phase 2 | What tests exist, what they cover, what they miss |
| `03-target-architecture.md` | Phase 3 | The exact target structure, conventions, and contracts |
| `04-test-strategy.md` | Phase 4 | The full test suite design, test by test |
| `05-refactor-plan.md` | Phase 5 | The numbered, TDD-first, step-by-step execution plan |
| `06-execution-protocol.md` | Phase 5 | The exact procedure a future Claude follows to execute one step |
| `harness-drafts/` | Phase 6 | Draft CLAUDE.md, skills, scripts, lint and CI configs, ready to be applied by plan steps |
| `README.md` | Phase 7 | Executive summary for the human owner |

## B.5 Working method

- Begin by creating `docs/refactor/` and `PROGRESS.md`.
- Use parallel subagents for independent scanning work when available (for example: one agent per top-level directory for Phase 1, or one per finding category). Give each subagent the exact rubric from this document and require it to return findings in the exact table format. Merge results yourself and de-duplicate.
- When counting or listing, prefer deterministic commands over reading. Record each command and its output summary in the report.
- Write each report section as soon as its evidence is gathered. Do not wait until the end of a phase to write.
- Before marking a phase complete, run the phase's self-check list (given at the end of each phase) and fix anything that fails.

---

# PHASE 0: INVENTORY AND RECONNAISSANCE

**Output:** `docs/refactor/00-inventory.md`

**Goal:** A complete, factual description of what exists. No opinions in this file. Every later phase refers back to it.

## 0.1 Repository basics

Record:

- Repository root path, git remote(s), default branch, current branch, latest commit hash and date, total commit count, number of contributors (from git log).
- Whether this is a monorepo (multiple packages/apps) or a single app. List every package/app with its path.
- Top-level directory tree to depth 3, with file counts and total lines per directory. Use a code-counting tool if available (`cloc`, `tokei`, `scc`); otherwise use `find` plus `wc -l`. Exclude `node_modules`, `.git`, build output, vendored dependencies, lockfiles, and generated files, and list exactly what you excluded.
- Languages used, with line counts per language.
- The 50 largest source files by line count, with path and count.
- The 50 largest source files by byte size if different.
- Total count of source files and total source lines.

## 0.2 Technology stack

For each of the following, record the exact tool, exact version (from lockfile or manifest), and the config file path:

- Runtime (Node, Deno, Bun, Python, etc.) and the version pinned (`.nvmrc`, `engines`, `.tool-versions`, Dockerfile, etc.). If not pinned, say so.
- Package manager and lockfile presence.
- Frontend framework (Next.js, React, Vue, Svelte, Astro, plain HTML, etc.) and rendering mode (SSR, SSG, SPA, mixed).
- Backend framework or API layer (Next.js API routes, Express, Fastify, serverless functions, Supabase edge functions, etc.).
- Database engine and hosting (Postgres on Supabase, PlanetScale MySQL, MongoDB Atlas, Firebase, SQLite, etc.).
- Database access method (ORM such as Prisma/Drizzle/TypeORM, query builder such as Kysely/Knex, raw SQL, a hosted client SDK such as `@supabase/supabase-js`).
- Migration tooling and the location of migration files. Count the migrations. Note whether the migration history looks linear and complete.
- Authentication provider and method (NextAuth, Clerk, Supabase Auth, Auth0, custom JWT, sessions).
- Payment or financial integrations (Stripe, Plaid, banking APIs, crypto, etc.).
- Any other third-party services (email, SMS, analytics, error tracking, feature flags, CMS, search, storage, queues, cron).
- Styling approach (Tailwind, CSS modules, styled-components, plain CSS, UI kit such as shadcn/MUI/Chakra).
- State management libraries (Redux, Zustand, Jotai, React Query/TanStack Query, SWR, context only).
- Form and validation libraries (react-hook-form, Formik, zod, yup, joi, class-validator).
- Testing tools present (Jest, Vitest, Mocha, Playwright, Cypress, Testing Library, Storybook, MSW).
- Linting and formatting tools and whether their configs exist and are non-trivial (ESLint config, Prettier config, EditorConfig, Stylelint).
- Type checking: TypeScript present? `strict` mode on? List every compiler option that weakens checking (`strict: false`, `noImplicitAny: false`, `strictNullChecks: false`, `skipLibCheck`, etc.).
- Build tool and bundler.
- Hosting and deployment (Vercel, Netlify, AWS, Fly, Render, Docker, etc.) and how deploys are triggered.
- CI/CD configuration (GitHub Actions, etc.). List every workflow and what it does. If none, say "No CI."
- Environment variable handling: list every env var name referenced in code (search for `process.env.`, `import.meta.env.`, `Deno.env`, `os.environ`, etc.), where each is read, whether a `.env.example` exists and whether it is complete.
- Containerization (Dockerfile, docker-compose).
- Any existing `CLAUDE.md`, `.claude/` directory, `.cursorrules`, `AGENTS.md`, or similar AI instruction files. Quote their full contents in an appendix.
- Any existing architecture docs, READMEs, ADRs, or wikis in the repo. List them with a one-line description each.

## 0.3 Application surface

- **Pages/routes**: list every user-facing route with its file path. For frameworks with file-based routing, derive from the directory. Note which are public, which require auth, and how you determined that.
- **API endpoints**: list every HTTP endpoint (method, path, file). Note auth requirements, input validation presence, and response shape consistency.
- **Server actions / RPC / edge functions**: list each.
- **Background jobs, cron, webhooks**: list each with trigger and file.
- **Database schema**: list every table/collection with its columns, types, nullability, primary key, foreign keys, indexes, and constraints. Pull from migrations, ORM schema, or the live schema dump if a read-only connection is available and safe. Note tables that appear unused by code.
- **Entity relationship summary**: a text or Mermaid diagram of the main entities and relationships.
- **External calls**: every outbound HTTP call to a third party, with file and purpose.
- **Shared/common code**: every directory that appears to be shared across features (`utils`, `lib`, `helpers`, `common`, `shared`, `core`), with file counts.

## 0.4 Dependency inventory

- Every production dependency with version and a one-line purpose. Flag any that appear unused (search for imports). Flag duplicates in purpose (two date libraries, two HTTP clients, two validation libraries, two state libraries).
- Every dev dependency, same treatment.
- Run the package manager's audit command (read-only) and record the count of vulnerabilities by severity and the top 10 by severity.
- Record any dependencies more than two major versions behind current, if that information is obtainable offline from the lockfile and registry metadata; otherwise mark `UNVERIFIED`.

## 0.5 Build, test, and quality baseline

Run each of the following if the project defines it, and record the exact command, wall-clock time, and result summary. Do not fix anything.

- Install (if not already installed).
- Type check.
- Lint.
- Format check.
- Unit/integration test suite. Record: number of test files, number of tests, pass/fail/skip counts, total time, and any flaky-looking behavior if you run it twice.
- Coverage report if configured. Record line, branch, function coverage overall and per top-level directory.
- Production build. Record time and output size. For web bundles, record the JS size per route or chunk if the build prints it.
- End-to-end test suite if present (do not run it against production; only run if it is configured for a local or test environment).

If any of these are not defined, record "Not configured" for each.

## 0.6 Internal dependency graph

- Generate an import/dependency graph between source directories. Use `madge`, `dependency-cruiser`, or equivalent if available or installable without modifying project files (install to a temp directory or use `npx` with an explicit version). If unavailable, build an approximate graph by parsing import statements with grep.
- Record: count of circular dependencies and list every cycle. Record the most-imported files (fan-in top 30) and the files that import the most (fan-out top 30).
- Identify which directories import from which (a directory-level adjacency list). This is the primary evidence for layering violations in Phase 1.

## 0.7 Git history signals

- The 30 most frequently changed files in the last 12 months (`git log --since --name-only`, count). High-churn files are where edit cost concentrates.
- Files that frequently change together (co-change coupling): find the top 20 pairs of files that appear in the same commit most often. These indicate hidden coupling.
- Average and median commit size (files changed). Very large average commits suggest changes ripple widely.
- Any commits whose message indicates a regression fix, revert, or hotfix in the last 12 months. Count them and list the 20 most recent with the files they touched.

## 0.8 Phase 0 self-check

Before marking Phase 0 complete, confirm in `PROGRESS.md`:

- [ ] Every item in 0.1 through 0.7 has either a filled-in value or an explicit `Not configured` / `UNVERIFIED: <reason>` entry.
- [ ] Every route, endpoint, table, and env var is listed individually, not summarized as "about 20 routes."
- [ ] Every command you ran is recorded with its output summary.
- [ ] No opinions or recommendations appear in `00-inventory.md`.

---

# PHASE 1: ARCHITECTURE AND CODE QUALITY AUDIT

**Output:** `docs/refactor/01-findings.md` plus appendix files

**Goal:** Every structural problem, with evidence, severity, and a direct link to the owner's symptoms.

## 1.1 Finding format

Every finding is one row in a table, and findings are grouped by category. Each finding gets a stable ID (`ARCH-001`, `DUP-014`, `DATA-003`, etc.) that later phases reference. The columns:

| ID | Severity | Location(s) | Evidence | Why it matters (symptom link) | Exact fix | Plan step |
|---|---|---|---|---|---|---|

- **Severity**: `CRITICAL` (security, data integrity, money correctness, or the site can break silently), `HIGH` (directly causes the owner's symptoms on common edits), `MEDIUM` (causes friction or risk on less common edits), `LOW` (hygiene).
- **Location(s)**: every `file:line-line` where the issue appears. If more than 5, put the full list in an appendix and reference it.
- **Evidence**: a short quoted snippet (max 6 lines) or the command output that proves the finding.
- **Why it matters**: which of the four symptoms (slow edits, token cost, edits not landing, regressions) this causes, and the specific mechanism. Example: "Price formatting is implemented in 6 places; a request to 'change how prices display' will be applied to whichever one Claude finds first, leaving 5 unchanged. Symptom 3."
- **Exact fix**: the concrete action, with target file paths and function/type names. This is a one-paragraph preview; the full procedure goes in Phase 5.
- **Plan step**: filled in during Phase 5 with the step number(s) that resolve it.

## 1.2 Categories and detection procedures

Work through every category. For each, run the detection procedure across the whole source tree, record every instance, then write the findings.

### Category ARCH: Boundaries and layering

Detect:

- UI components or pages that directly query the database or call a database client SDK. (Search for the DB client import in files under the UI/pages/components directories.)
- Business logic (calculations, rules, validations, state transitions) living inside UI components, route handlers, or page files rather than in a dedicated logic layer. Heuristic: functions longer than 20 lines inside a component or handler that do not render UI or parse the request.
- Route handlers or server actions that contain more than request parsing, calling one service function, and formatting the response.
- Circular imports (from 0.6). Every cycle is a finding.
- Modules that reach into another module's internals (importing from a deep path inside another feature rather than from its index/public interface).
- "Shared" directories (`utils`, `lib`, `helpers`, `common`) that have become dumping grounds: list each file in them and classify it as truly cross-cutting (used by 3+ features) or feature-specific (used by 1 feature, belongs in that feature).
- Barrel files (`index.ts` re-exporting everything) that cause large import graphs and make it impossible to know what is actually used.
- God files: any file over 300 lines. Any function over 50 lines. Any component over 200 lines. Any file exporting more than 10 symbols. List all in an appendix with counts; summarize as findings per directory.
- Absence of an explicit module/feature structure: is code organized by technical type (`components/`, `hooks/`, `services/`, `types/` at the top level, each containing every feature) rather than by feature? Document which it is and what the cost is.
- Framework coupling: business logic that imports framework-specific objects (request, response, React hooks, router) and therefore cannot be unit tested without the framework.

### Category DUP: Duplication and multiple sources of truth

Detect:

- Duplicated functions: use a duplication detector (`jscpd` via `npx jscpd@<pinned version> --min-tokens 50 --reporters console,json --output <tempdir>`, or equivalent for the language) and record every duplicate block with both locations. Put the full list in `01-findings-appendix-duplication.md`.
- Semantic duplicates the tool will miss: search for multiple implementations of the same concept. Check at minimum: currency/number formatting, date formatting and parsing, fetch/API client wrappers, error handling wrappers, auth checks ("is user logged in", "is user admin"), input validation for the same entity, pagination logic, environment variable reading, logging, and any domain calculation (interest, fees, balances, returns, scores).
- Types or schemas defined more than once for the same entity (for example, a `User` type in the frontend, another in the backend, and a third as a DB model, with no single source).
- Constants and magic values repeated (status strings, role names, currency codes, limits, URLs).
- Duplicated UI patterns (the same form, table, card, or modal structure copy-pasted with small variations).

### Category DATA: Data layer

Detect:

- Raw SQL or DB client calls scattered across many files rather than in a repository/data-access layer. Count the files that touch the DB directly.
- Queries without pagination or limits on tables that can grow.
- N+1 query patterns (a query inside a loop, or a per-item fetch after a list fetch).
- Missing transactions around multi-step writes that must be atomic (especially anything touching balances, orders, payments, or related rows across tables).
- Schema issues from 0.3: missing primary keys, missing foreign keys, missing indexes on columns used in `WHERE`/`JOIN`/`ORDER BY`, columns that are nullable but never null in code (or vice versa), use of floating point for money, missing `created_at`/`updated_at`, missing unique constraints where the code assumes uniqueness, enum-like strings without constraints.
- Migration health: migrations edited after being applied, missing down migrations, manual schema changes not reflected in migrations, drift between ORM schema and migration files.
- Authorization at the data layer: can a query return another user's data if the caller forgets a `WHERE user_id = ?`? Is row-level security used if the DB supports it? List every query that reads or writes user-owned data and whether it is scoped to the current user.
- Soft-delete, audit trail, and idempotency handling for financial records.
- Seed data and test database setup: does any exist?

### Category API: API and contract layer

Detect:

- Endpoints without input validation (reading `req.body` fields directly without a schema).
- Inconsistent response shapes across endpoints (some return `{ data }`, some return the object directly, some return `{ error: string }`, some throw).
- Inconsistent error handling (some endpoints return 500 with stack traces, some return 200 with an error field).
- Missing authentication or authorization checks on endpoints that need them. List every endpoint and its check.
- Types shared between client and server by copy rather than by a shared schema (e.g., a zod schema that both sides import).
- Hardcoded URLs or environment-specific values in client code.
- Secrets or server-only env vars referenced from client-side code (anything bundled to the browser).
- Missing rate limiting on authentication, password reset, payment, or other sensitive endpoints.
- CORS configuration.

### Category TYPE: Type safety

Detect (for TypeScript or typed languages):

- Count of `any` (explicit), `as any`, `as unknown as`, `@ts-ignore`, `@ts-expect-error`, `!` non-null assertions. List all in an appendix.
- `strict` mode status and each weakened option (from 0.2).
- Untyped external data: JSON parsed and used without validation.
- Functions with no return type that return different shapes on different paths.
- For JavaScript codebases: absence of types entirely is itself a HIGH finding with a migration recommendation (JSDoc or incremental TS).

### Category ERR: Error handling, logging, and observability

Detect:

- Empty catch blocks or catch blocks that only `console.log`.
- `console.log`/`console.error` used as the logging system; count instances.
- Errors swallowed and converted to `null`/`undefined`/default values without signaling.
- No error boundary in the UI (React) or equivalent.
- No error tracking service wired in, or wired in but not used in catch blocks.
- Inconsistent error types (strings, plain objects, Error subclasses mixed).
- Lack of structured logging with request IDs or user IDs for tracing a problem through the system.

### Category SEC: Security

Detect:

- Secrets in the repo (search for patterns: `sk_live`, `sk_test`, `AKIA`, `-----BEGIN`, `password =`, `api_key =`, `token =`, long base64 strings in config, `.env` files committed). Check git history too (`git log -p --all -S <pattern>` for the most common patterns) and note if a secret was ever committed even if since removed.
- Injection: SQL built by string concatenation, HTML rendered from user input without escaping (`dangerouslySetInnerHTML`, `innerHTML`, `v-html`), shell commands built from input.
- Auth: session handling, token storage (localStorage vs httpOnly cookies), password hashing algorithm, missing CSRF protection on state-changing requests if cookies are used.
- Authorization: endpoints or pages that check "logged in" but not "allowed to access this specific resource."
- Dependency vulnerabilities (from 0.4).
- Missing security headers (CSP, HSTS, X-Frame-Options) if the framework config is visible.
- File upload handling without type/size validation, if present.
- Financial-specific: amounts accepted from the client without server-side recomputation, price or fee values trusted from the request body, missing idempotency keys on payment creation, webhook endpoints without signature verification.

### Category PERF: Performance

Detect:

- Bundle size issues from the build output (0.5): any route over 300 KB of JS, large libraries imported in full (`import _ from 'lodash'`, moment.js, full icon packs).
- Images not optimized or not using the framework's image component.
- Client-side data fetching waterfalls (a component fetches, then a child fetches based on the result).
- Missing caching on expensive or frequently repeated reads.
- Unbounded queries (from DATA).
- Expensive computation in render paths or on every request that could be memoized or precomputed.
- Missing database indexes (from DATA).
- Blocking third-party scripts.

### Category CFG: Configuration and environments

Detect:

- Env vars read in many places rather than through one validated config module.
- No validation that required env vars are present at startup (the app fails deep inside a request instead of at boot).
- Missing or incomplete `.env.example`.
- Hardcoded environment-specific values (URLs, IDs, feature flags) in code.
- No distinction between development, test, and production config.
- No local development setup documented or scripted.

### Category DEAD: Dead code and clutter

Detect:

- Unused exports (use `ts-prune`, `knip`, or equivalent via `npx` with a pinned version; otherwise grep for each export's usage). List in an appendix.
- Unused dependencies (from 0.4).
- Commented-out code blocks over 5 lines. Count and list.
- `TODO`, `FIXME`, `HACK`, `XXX` comments. Count and list with age from git blame.
- Files not imported by anything and not an entry point.
- Feature flags or branches for features that are fully launched or fully abandoned.
- Multiple versions of the same component (`Button`, `ButtonNew`, `ButtonV2`).

### Category TOOL: Build and tooling hygiene

Detect:

- Linter absent, or present with a trivial config, or present but with many disabled rules or many `eslint-disable` comments (count them).
- Formatter absent or inconsistently applied (run the format check and count files that would change).
- No pre-commit hooks.
- No CI, or CI that does not run tests, or CI that runs tests but allows failure.
- No single command that runs all checks (`lint + typecheck + test + build`).
- Test command slow (over 60 seconds for unit tests) or requiring manual setup.
- Runtime version not pinned.
- Lockfile missing or not committed.

### Category AI: AI-ergonomics (the harness)

This category is specifically about what makes the codebase expensive and error-prone for Claude to edit. Detect:

- **No or weak `CLAUDE.md`**: absent, or present but missing any of: how to run tests, how to run the app, where features live, the module structure rule, naming conventions, the "one command to verify" instruction, and the list of skills.
- **No skills**: no `.claude/skills/` with procedures for the recurring tasks. List what recurring task types the git history shows (from 0.7: what kinds of changes are made most often) and note that no skill exists for each.
- **Discoverability**: can the file for a given feature be found by name alone? Check: are there generic file names (`index.ts`, `utils.ts`, `helpers.ts`, `types.ts`, `component.tsx`) that give no information? Count files with generic names. Are feature names in the code the same as the names a user would use on the website? List mismatches (e.g., the UI says "Portfolio" but the code says `holdings`).
- **File size budget violations**: any file Claude must read in full to make a typical edit that exceeds 300 lines. These dominate token cost. List with line counts (from ARCH god-file list) and estimate tokens (lines × ~12 as a rough rule).
- **Implicit conventions**: patterns that are followed consistently but documented nowhere (so Claude must infer them by reading several files each time). List each one you detect.
- **Colocated tests**: are tests next to the code they test, or in a separate tree that must be searched separately? Which?
- **Missing module interfaces**: for each feature area, is there a single file that defines what it exposes? If not, Claude must read every file in the folder to know what is available.
- **Non-deterministic or undocumented commands**: anything that requires knowing a manual sequence (start DB, run migrations, seed, start dev server) without a script that does it.
- **Estimated context cost of a typical edit**: pick the 5 most common change types from git history (0.7). For each, trace which files a careful engineer would need to read to make the change correctly today, and sum their lines. This is the direct measure of symptoms 1 and 2. Record it as a baseline so the post-refactor state can be compared.

## 1.3 Cross-cutting analysis

After filling in all categories, add a section that:

- Maps each finding to the four symptoms and produces a count per symptom per severity.
- Identifies the top 10 findings by expected impact on the owner's symptoms, with reasoning.
- Identifies "root" findings that cause many others (e.g., "no module structure" causes most DUP and ARCH findings). These become the earliest refactoring steps.
- Explicitly evaluates the owner's hypothesis: state whether the codebase has a thin harness, fat skills, and isolated modules, with the evidence for each of the three, and a one-sentence verdict.

## 1.4 Phase 1 self-check

- [ ] Every category in 1.2 has at least one finding or an explicit "No instances found; detection method: <command>."
- [ ] Every finding has a `file:line` location or an appendix reference.
- [ ] Every finding has a severity and a symptom link.
- [ ] No finding uses the words "consider," "might," "could improve," or "etc." in the fix column.
- [ ] The duplication, god-file, type-escape, and dead-code appendices are complete lists, not samples.
- [ ] Section 1.3 is filled in, including the hypothesis verdict.

---

# PHASE 2: TEST COVERAGE AUDIT

**Output:** `docs/refactor/02-test-coverage-audit.md`

**Goal:** Know exactly what is protected by tests today and what is not, so the refactor can be sequenced safely.

## 2.1 Existing tests

- List every test file with path, the framework it uses, the number of tests, and what module or behavior it tests (one line each).
- For each test, classify: unit (pure logic, no I/O), integration (hits a real DB or service), component (renders UI), end-to-end (drives a browser), or snapshot. Count per class.
- Assess quality, with examples cited by `file:line`: tests that assert nothing meaningful (`expect(true).toBe(true)`, only checking "does not throw"), tests that are tautological (assert the mock returns what the mock was told to return), tests that are skipped, tests that depend on execution order, tests that hit production services, tests that use real time or random values without control.
- Record the coverage report from Phase 0 per directory. Identify every source directory with 0% coverage.
- Test runtime: total, and the 10 slowest tests.
- Test infrastructure present: factories, fixtures, mocks, test DB setup, MSW handlers, Playwright config. List each or note absence.

## 2.2 Critical path map

Independently of what tests exist, enumerate the behaviors that must never break. Build this from the route list, endpoint list, and schema (Phase 0). At minimum consider:

- Authentication: sign-up, sign-in, sign-out, password reset, session expiry, OAuth callback.
- Authorization: every resource a user owns can be read/modified only by them (or by allowed roles).
- Every money-related calculation: list each formula found in the code with its location and inputs.
- Every write that changes a balance, status, ownership, or financial record.
- Every payment provider interaction: create, confirm, refund, webhook handling.
- Every external integration that the site depends on to function.
- Every form the user can submit: validation rules, success path, each error path.
- Every page's primary content loading for a logged-in and a logged-out user.
- Data integrity: constraints the code assumes (uniqueness, non-null, referential integrity).
- Scheduled jobs and their idempotency.

For each critical behavior, record: ID (`CP-001`...), description, where it is implemented (`file:line`), whether any existing test covers it (test file or "NONE"), and risk if it regresses (`CRITICAL`/`HIGH`/`MEDIUM`).

## 2.3 Gap summary

- Count of critical paths with no test coverage, by risk level.
- The 20 most dangerous gaps, ranked.
- Infrastructure gaps that block writing good tests (no test DB, no factories, no way to run the app in test mode, no API mocking, tightly coupled code that cannot be tested without the framework).

## 2.4 Phase 2 self-check

- [ ] Every test file is listed and classified.
- [ ] The critical path map covers every route, endpoint, and financial calculation from Phase 0.
- [ ] Every critical path has a coverage status.
- [ ] Infrastructure gaps are listed with what each blocks.

---

# PHASE 3: TARGET ARCHITECTURE DESIGN

**Output:** `docs/refactor/03-target-architecture.md`

**Goal:** Specify, exactly, the structure the code should have after the refactor. This must be concrete enough that every Phase 5 step can say "move X to Y" with no ambiguity. Adapt everything below to the real stack found in Phase 0.

## 3.1 Design principles (state these, then apply them)

1. **Feature modules, not technical layers, at the top level.** Code is grouped by what it does for the user, not by what kind of file it is.
2. **Each module has one public interface file.** Everything else in the module is private. Other modules import only from the interface.
3. **Dependency direction is one-way.** UI depends on application logic; application logic depends on domain logic and on data-access interfaces; data access implements those interfaces. Nothing depends upward. Enforced by lint rules, not by convention.
4. **Framework-free core.** Domain and application logic has no imports from the web framework, the DB client, or the UI library, so it can be unit tested in milliseconds with no setup.
5. **One source of truth per concept.** Each entity has one schema (e.g., a zod schema) from which its TypeScript type, its validation, and ideally its DB type derive. Each formatting rule, each calculation, each constant exists once.
6. **File size budgets.** Files under 200 lines (hard limit 300), functions under 40 lines, components under 150 lines. Budgets enforced by lint.
7. **Tests live next to the code they test** and are named `<file>.test.<ext>`. Each module can run its own tests in isolation.
8. **Every recurring task has a skill.** The procedure for adding a page, endpoint, table, migration, module, or calculation is written once in `.claude/skills/<task>/SKILL.md`.
9. **One command verifies everything.** `npm run check` (or equivalent) runs format check, lint, typecheck, and tests. It must pass before any commit. CI runs the same command.
10. **Boring, explicit, discoverable names.** Files and folders are named for the user-facing concept, matching the words on the website. No `utils.ts`, `helpers.ts`, `misc.ts`, `index.ts` except as module interface files.

## 3.2 Target directory layout

Produce the full target tree. Below is a reference shape for a TypeScript web app; translate to the real stack and real feature names discovered in Phase 0. Every feature found in Phase 0 must appear as a module here.

```
/
├── CLAUDE.md                      # Thin harness: <150 lines. Points to everything else.
├── .claude/
│   └── skills/
│       ├── add-page/SKILL.md
│       ├── add-api-endpoint/SKILL.md
│       ├── add-db-table-or-column/SKILL.md
│       ├── add-feature-module/SKILL.md
│       ├── change-calculation/SKILL.md
│       ├── fix-bug/SKILL.md          # Reproduce with a failing test first
│       ├── add-ui-component/SKILL.md
│       └── run-and-verify/SKILL.md
├── docs/
│   ├── architecture.md            # This document's 3.x sections, trimmed
│   ├── adr/                       # Architecture decision records, one per decision
│   └── refactor/                  # Output of this brief
├── scripts/
│   ├── check.sh                   # format + lint + typecheck + test
│   ├── dev.sh                     # start DB, migrate, seed, start app
│   ├── test-db-reset.sh
│   └── ...
├── src/
│   ├── app/                       # Framework shell ONLY: routes, layouts, providers, wiring
│   │   └── (routes mirror the framework's convention; each route file is <40 lines
│   │        and only calls into a module's public interface)
│   ├── modules/
│   │   ├── <feature-a>/           # e.g. accounts, portfolio, transactions, onboarding
│   │   │   ├── index.ts           # PUBLIC INTERFACE: the only file others may import
│   │   │   ├── README.md          # <60 lines: what this module owns, its interface, how to test it
│   │   │   ├── domain/            # Pure logic: entities, calculations, rules. No I/O.
│   │   │   │   ├── <entity>.ts
│   │   │   │   ├── <entity>.test.ts
│   │   │   │   ├── <calculation>.ts
│   │   │   │   └── <calculation>.test.ts
│   │   │   ├── schema/            # Single source of truth: zod schemas + derived types
│   │   │   │   ├── <entity>.schema.ts
│   │   │   │   └── <entity>.schema.test.ts
│   │   │   ├── application/       # Use cases: orchestrate domain + repositories. No framework.
│   │   │   │   ├── <use-case>.ts
│   │   │   │   └── <use-case>.test.ts
│   │   │   ├── data/              # Repository implementations. Only place that touches the DB.
│   │   │   │   ├── <entity>.repository.ts
│   │   │   │   ├── <entity>.repository.integration.test.ts
│   │   │   │   └── <entity>.repository.fake.ts   # In-memory fake for use-case tests
│   │   │   ├── api/               # Thin HTTP adapters: parse → call use case → respond
│   │   │   │   ├── <endpoint>.handler.ts
│   │   │   │   └── <endpoint>.handler.test.ts
│   │   │   └── ui/                # Components for this feature only
│   │   │       ├── <Component>.tsx
│   │   │       └── <Component>.test.tsx
│   │   └── <feature-b>/ ...
│   ├── shared/                    # ONLY truly cross-cutting code, each in its own folder with tests
│   │   ├── money/                 # Money type, formatting, arithmetic (integer cents, never float)
│   │   ├── dates/
│   │   ├── result/                # Result<T, E> type for error handling
│   │   ├── errors/                # AppError hierarchy
│   │   ├── logger/
│   │   ├── config/                # Validated env loading; the only place process.env is read
│   │   ├── http/                  # Response envelope, error-to-status mapping, API client
│   │   ├── auth/                  # Session reading, "current user" helpers, authorization guards
│   │   └── ui/                    # Design-system primitives only (Button, Input, Card, Modal)
│   └── db/
│       ├── client.ts              # The single DB client instance
│       ├── migrations/
│       ├── seed/
│       └── test-utils/            # Test DB lifecycle helpers
├── e2e/                           # Playwright: critical journeys only
└── (config files)
```

For every module in the target tree, write a short table: module name, user-facing concept it corresponds to, the current files (from Phase 0/1) that will move into it, and the public interface it will expose (function and type names).

## 3.3 Conventions to specify exactly

For each of the following, write the rule, a code example in the real stack, and the lint rule or test that enforces it:

- **Module public interface**: what `index.ts` may export (use cases, schemas, types, UI components; never repositories or internal helpers).
- **Import rules**: `app/` may import from `modules/*/index` and `shared/*`. `modules/<a>` may import from `shared/*` and from `modules/<b>/index` only. `domain/` may import from `shared/*` only (and nothing with I/O). `data/` is the only place that imports the DB client. Specify the exact `eslint-plugin-boundaries` or `dependency-cruiser` configuration that enforces this.
- **Schema-first types**: each entity defined once as a zod (or equivalent) schema; TS type derived via `z.infer`; input validation uses the same schema; DB row mapping is explicit and tested.
- **Money**: stored and computed as integer minor units (cents) in a `Money` type; formatted only at the UI edge via one function; never `number` with decimals for currency. If the current DB uses float/decimal columns for money, specify the migration path.
- **Error handling**: use cases return `Result<T, AppError>` (or throw typed `AppError` subclasses; pick one and justify). HTTP adapters map error types to status codes in one place. UI shows errors via one pattern. No empty catches; lint rule `no-empty` plus a custom rule or review check.
- **Logging**: one logger, structured (JSON in production), with request ID and user ID attached. `console.*` banned by lint outside the logger module.
- **Config**: one `config.ts` that reads and validates all env vars at startup with a schema and exports a typed object. `process.env` banned by lint everywhere else.
- **Data access**: repository interface defined in `application/` or `domain/`, implemented in `data/`, with an in-memory fake for tests. Every query that touches user-owned data takes the user/tenant ID as a required parameter (not optional).
- **API responses**: one envelope shape (`{ ok: true, data } | { ok: false, error: { code, message } }` or the chosen equivalent). One helper to produce it. Document the HTTP status mapping.
- **Authorization**: one guard helper per pattern (`requireUser`, `requireOwner(resource)`, `requireRole`). Every handler calls one. A test asserts every handler file imports a guard.
- **UI components**: props typed, no data fetching inside presentational components, feature components in their module, primitives in `shared/ui`. Component files under 150 lines; extract subcomponents.
- **Naming**: files kebab-case or the framework convention, components PascalCase, one exported component per file, test files `*.test.ts(x)`, integration tests `*.integration.test.ts`, no generic names. List the banned names.
- **File and function size**: ESLint `max-lines` (300 warn at 200), `max-lines-per-function` (40), `complexity` (10).
- **Comments and docs**: each module has a README; each non-obvious decision gets an ADR; no commented-out code (lint rule or review check).
- **Database**: every table has `id`, `created_at`, `updated_at`; money columns are integer; foreign keys and indexes required; migrations are forward-only and never edited after merge; row-level security or equivalent policy per user-owned table (if supported by the DB).

## 3.4 The harness design

Specify in detail:

**Root `CLAUDE.md`** (target under 150 lines). Must contain, in this order:

1. One paragraph: what the product is.
2. The one verification command and the rule that it must pass before any commit.
3. How to run the app locally (one command).
4. The module map: a table of every module, its user-facing name, and its path.
5. The import rules in five lines.
6. The size budgets in three lines.
7. The list of skills and when to use each (one line per skill).
8. The rule: "Before editing, read the module's README.md and index.ts. Do not read other modules unless the README says they are involved."
9. The rule: "Every behavior change starts with a failing test."
10. Pointers to `docs/architecture.md` and `docs/adr/`.

**Skills** (each `SKILL.md` under 120 lines): for each skill listed in 3.2, specify its exact contents: the trigger ("use when the user asks to..."), the files to read first, the step-by-step procedure, the tests that must be written, the verification command, and the definition of done. Phase 6 writes the drafts.

**Module READMEs** (each under 60 lines): template with: purpose, user-facing names, public interface summary, data owned (tables), key invariants and rules, how to run this module's tests, known gotchas.

**Scripts**: `check`, `dev`, `test`, `test:watch`, `test:module <name>`, `test:e2e`, `db:migrate`, `db:reset`, `db:seed`. Each a single command with no manual steps.

**Lint configuration**: the exact rule set enforcing 3.3.

**CI**: one workflow that runs `check` on every push and pull request, and e2e on the main branch, failing the build on any failure.

**Pre-commit hook**: runs format and lint on staged files (lint-staged + husky or the stack's equivalent).

## 3.5 Expected impact

For each of the 5 common change types traced in Phase 1 (category AI, "estimated context cost of a typical edit"), trace the same change in the target architecture: which files would need to be read, and their expected line counts. Present before/after in a table. This is the quantitative justification for the refactor.

## 3.6 Decisions and alternatives

For each significant decision (module structure, error-handling style, schema library, test framework, lint tooling, state management approach, data access pattern), write a short ADR-style entry: context, decision, alternatives considered, why rejected. These become `docs/adr/` files in Phase 6.

## 3.7 Phase 3 self-check

- [ ] Every feature from Phase 0 is placed in the target tree with its current files mapped.
- [ ] Every convention in 3.3 has a rule, a real-stack example, and an enforcement mechanism.
- [ ] The harness design specifies the full contents of CLAUDE.md and every skill.
- [ ] The before/after context cost table is filled.
- [ ] Nothing in this document is stack-generic; every example uses the real framework, DB, and libraries.

---

# PHASE 4: TEST STRATEGY DESIGN

**Output:** `docs/refactor/04-test-strategy.md`

**Goal:** Design the complete test suite that will (a) lock in current behavior before refactoring and (b) protect every critical path permanently, running fast enough that it is run on every change.

## 4.1 Test levels and their rules

Define each level with: what it tests, what it may touch, target speed, where it lives, naming, and the tooling.

- **Unit tests** (domain, schema, application with fake repositories): pure, no I/O, no framework. Target: entire unit suite under 10 seconds. Live next to the code.
- **Integration tests** (repositories against a real test database; HTTP handlers against the real use cases with the test DB): each test in a transaction rolled back, or a fresh schema per file. Target: under 60 seconds total. Specify the test DB approach for the actual DB engine (Docker Postgres, Supabase local, SQLite in-memory for compatible code, Testcontainers, etc.).
- **Contract tests**: every API endpoint's request and response validated against its schema; the frontend API client tested against the same schema. These catch client/server drift.
- **Component tests** (Testing Library or framework equivalent): render with props, assert on accessible roles and text, interact, assert. No snapshot tests except for pure design-system primitives.
- **End-to-end tests** (Playwright): only the critical journeys, against a locally running app with a seeded test DB. Target: under 10 journeys, under 5 minutes. Specify how auth is handled in E2E (seeded test user, storage state reuse).
- **Characterization (golden master) tests**: for every existing calculation, formatter, and data transformation that will be refactored, a test that feeds a fixed set of inputs through the CURRENT code and records the outputs as the expected values. These are written BEFORE any refactoring step and must stay green through the refactor. Specify the input sets for each (include edge cases: zero, negative, very large, rounding boundaries, empty, null, unicode, timezone edges).
- **Static tests**: typecheck, lint (including import boundary rules and size budgets), format check, dependency cruiser for cycles, a test that fails if any file in `src/` reads `process.env` outside `shared/config`, a test that fails if any handler lacks an auth guard, a test that fails if `console.` appears outside the logger.

## 4.2 Test infrastructure to build

Specify exactly, with file paths and the libraries to use:

- Test runner config (Vitest or Jest; recommend based on the stack, justify).
- Test database lifecycle: how it starts, migrates, seeds, resets between tests, and tears down. One script.
- Factories for every entity (e.g., `makeUser()`, `makeTransaction({ amount: 1000 })`) using a factory library or plain functions; defaults valid, overrides allowed, deterministic IDs and dates.
- Fake repository implementations (in-memory) for every repository interface, so use-case tests need no DB.
- HTTP mocking for third parties (MSW or equivalent) with recorded fixtures for every external API the app calls, especially payment providers. Never call a real third party in tests.
- Time control (fake timers / injected clock) so nothing depends on the real date.
- Playwright config with the local app, seeded DB, and auth storage state.
- Coverage configuration with thresholds that fail the build: start at the current baseline, with a plan to raise it per phase to a target (recommend: 90% lines on `domain/` and `application/`, 80% on `data/` and `api/`, 60% on `ui/`; 100% on every money calculation).
- CI job matrix: unit+static on every push, integration on every push, e2e on main and on PRs touching `app/` or `e2e/`.

## 4.3 Test inventory

This is the core deliverable of Phase 4. Produce a table of every test to be written, derived from the Phase 2 critical path map and the Phase 3 target architecture:

| Test ID | Level | Target file (where the test lives) | What it asserts (specific) | Covers critical path(s) | Written in plan step |
|---|---|---|---|---|---|

Requirements:

- Every critical path `CP-xxx` from Phase 2 appears in at least one test's "Covers" column. Critical paths rated CRITICAL appear at unit AND integration or E2E level.
- Every money calculation gets: a characterization test (now), unit tests for normal cases, boundary cases (0, max, rounding at .5 and .005, negative if applicable), and a property-based test if the stack supports it (`fast-check`), e.g., "sum of splits equals total," "fees never exceed principal," "formatting then parsing round-trips."
- Every API endpoint gets: a contract test, an auth test (unauthenticated → 401, wrong user → 403/404), a validation test (bad input → 400 with the envelope), and a happy path.
- Every repository gets: CRUD, user scoping ("cannot read another user's row"), and constraint tests.
- Every form gets: component tests for each validation rule and the submit path.
- Every page gets: a render test for logged-out and logged-in states.
- The assertions column is specific: "returns 403 when the transaction belongs to another user" not "tests authorization."

## 4.4 Regression protection protocol

Write the rule set that governs tests going forward:

- No behavior change without a test that failed before and passes after.
- No bug fix without a reproducing test first.
- Tests must be deterministic; a flaky test is fixed or deleted the day it flakes, never retried.
- `check` must pass before every commit; CI must pass before merge.
- Coverage thresholds only go up.
- Characterization tests may be replaced by proper unit tests once the code is refactored, but never deleted without a replacement that covers the same inputs.

## 4.5 Phase 4 self-check

- [ ] Every CP-xxx is covered by at least one planned test.
- [ ] Every money calculation has characterization, unit, boundary, and (if feasible) property tests planned.
- [ ] Every endpoint has contract, auth, validation, and happy-path tests planned.
- [ ] Test infrastructure is specified down to file paths and libraries.
- [ ] Target run times are stated for each level.

---

# PHASE 5: THE STEP-BY-STEP TDD REFACTORING PLAN

**Outputs:** `docs/refactor/05-refactor-plan.md` and `docs/refactor/06-execution-protocol.md`

**Goal:** An ordered sequence of small, safe, test-first steps that a future Claude session executes one at a time with a single command from the human, leaving the site working after every step.

## 5.1 Sequencing principles

Order the steps in this macro sequence. Within each stage, order by root-cause findings first (from 1.3), then by risk-adjusted impact on the owner's symptoms.

**Stage 0: Safety net (no behavior change, no code moves)**
- Pin runtime, add lockfile if missing.
- Add/upgrade test runner, lint, format, typecheck configs. Add `check` script. Add CI running `check`. Add pre-commit hook.
- Baseline coverage thresholds at current values so they cannot drop.
- Add test DB infrastructure, factories, MSW, fake clock.
- Write ALL characterization tests for every calculation, formatter, and transformer that will later move. These must be green against current code.
- Write auth and contract tests for every existing endpoint against current behavior (document current inconsistencies as the expected values for now; they will be tightened later).
- Write E2E tests for the top critical journeys against the current app.
- Fix CRITICAL security findings that are safe to fix in isolation (e.g., secret removal and rotation instructions, webhook signature verification, missing auth check), each with a test first. Security fixes are the only behavior changes allowed in Stage 0.
- Add the first version of `CLAUDE.md` describing the CURRENT structure honestly plus the new `check` command, so Claude is immediately more effective during the refactor itself.

**Stage 1: Foundations in `shared/`**
- Create `shared/config` with validated env; migrate every `process.env` read; lint rule bans others.
- Create `shared/logger`; migrate `console.*`; lint rule bans others.
- Create `shared/errors` and `shared/result`; define the error-handling convention.
- Create `shared/http` envelope and error mapping.
- Create `shared/money` and `shared/dates`; migrate every formatter instance (DUP findings) to the single implementation, characterization tests proving identical output.
- Create `shared/auth` guards.
- Each of these is one step, test-first, with a lint rule locking it in at the end of the step.

**Stage 2: Module extraction (strangler fig, one module at a time)**
- For each feature module in Phase 3's target tree, in order of (highest risk first? No: start with the lowest-risk, smallest module to prove the pattern, then proceed to highest-pain modules, leaving the most dangerous money-handling module until the pattern is well established and the test infrastructure is proven):
  1. Create the module folder, README, and empty `index.ts`.
  2. Define the schema (single source of truth) and derive types; write schema tests.
  3. Extract domain logic into `domain/` with unit tests (characterization tests already exist; add proper unit tests).
  4. Define the repository interface; implement in `data/` with integration tests and an in-memory fake.
  5. Extract use cases into `application/` with unit tests against the fake.
  6. Rewrite the module's HTTP handlers as thin adapters; contract and auth tests pass.
  7. Move the module's UI into `ui/`; component tests.
  8. Update `app/` routes to call only the module's `index.ts`.
  9. Delete the old code paths once all tests pass. Add the boundary lint rules for this module.
  10. Run E2E. Commit.
- Each sub-step is its own plan step so each is small.

**Stage 3: Data layer hardening**
- Migrations for missing constraints, indexes, foreign keys, money column types (with a tested data migration), audit columns, RLS policies. Each migration is one step with a test that asserts the constraint.
- Transaction wrapping for multi-step writes, with tests that assert atomicity (simulate a failure mid-write; assert nothing persisted).
- Pagination and limits on unbounded queries.

**Stage 4: API and UI consistency**
- Tighten the response envelope and status codes to the convention (now that contract tests exist, change the expected values deliberately, one endpoint at a time).
- Input validation on every endpoint via shared schemas.
- Rate limiting on sensitive endpoints.
- UI: migrate to design-system primitives, remove duplicated components, add error boundaries.

**Stage 5: Dead code, dependencies, performance**
- Remove unused exports, files, dependencies (each with the test suite proving nothing broke).
- Bundle size fixes (tree-shakeable imports, dynamic imports for heavy routes), with a bundle-size budget test.
- Caching and N+1 fixes with query-count assertions in integration tests.

**Stage 6: Harness finalization**
- Final `CLAUDE.md` reflecting the new structure.
- All skills written and tested by actually using them (the step includes: "use the add-page skill to add a trivial page, verify it took under N tool calls, then remove the page").
- Module READMEs complete.
- ADRs committed.
- Coverage thresholds raised to targets.
- Re-measure the context cost of the 5 common change types (from 1.2 AI / 3.5) and record before/after in `docs/refactor/RESULTS.md`.

## 5.2 Step format

Every step in `05-refactor-plan.md` uses exactly this template. No field may be omitted or left vague.

```markdown
## Step NNN: <imperative title, e.g., "Extract money formatting into shared/money">

**Stage:** <0-6>
**Resolves findings:** <IDs from Phase 1>
**Implements tests:** <Test IDs from Phase 4>
**Risk:** LOW | MEDIUM | HIGH
**Estimated size:** <number of files touched>, <approx lines changed>
**Depends on steps:** <list or "none">

### Goal
<One or two sentences: what is true after this step that was not true before.>

### Preconditions (verify before starting)
- `npm run check` passes on the current main branch.
- Steps <list> are complete (verify by checking PROGRESS.md and by confirming <specific file or test> exists).
- <Any other concrete, checkable precondition.>

### Files to read first (and nothing else)
- `path/to/file.ts` (lines a-b): <why>
- ...

### Tests to write FIRST (red)
For each test:
- **File:** `path/to/x.test.ts`
- **Test name:** `"<exact describe/it text>"`
- **Arrange:** <inputs, fixtures, factories used>
- **Act:** <the call>
- **Assert:** <exact expected values or shapes>
- **Expected to fail because:** <the function/module does not exist yet, or returns the old shape>

### Implementation (green)
Numbered, exact actions:
1. Create `path/to/new-file.ts` exporting `functionName(args: Types): ReturnType`. Body: <description of logic, or "move the body from `old/file.ts:41-88` unchanged">.
2. In `path/to/caller.ts:12`, replace `<old call>` with `<new call>`.
3. ...
Keep implementation minimal: only what the tests demand.

### Refactor (clean)
- <Specific cleanups allowed in this step, e.g., "rename `fmt` to `formatMoney`", "delete `old/file.ts:41-88` now that it is unused".>
- Do NOT: <specific things to avoid in this step to keep it small.>

### Lock-in
- Add lint rule / boundary rule / static test: <exact config change> so this cannot regress.

### Verification
1. `npm run test -- path/to/x.test.ts` → all new tests pass.
2. `npm run check` → passes with zero warnings.
3. <Characterization tests that must still pass: list>.
4. <If UI or API changed: the E2E test(s) to run.>
5. <Manual smoke check if any: exact URL and what to observe.>

### Commit
Message: `<type>(<module>): <title>` followed by a body listing the finding IDs resolved.

### Rollback
`git revert <this commit>` is safe because: <reason, e.g., no migration was applied>.
OR: <exact rollback procedure if a migration was involved, including the down migration file>.

### Definition of done
- [ ] All tests in "Tests to write FIRST" exist and pass.
- [ ] `check` passes.
- [ ] No file outside the "Files to read first" list and the listed new files was modified (verify with `git diff --stat`).
- [ ] PROGRESS.md updated with step number, commit hash, date.
```

## 5.3 Plan-level requirements

- Every finding ID from Phase 1 with severity CRITICAL or HIGH must appear in at least one step's "Resolves findings." MEDIUM and LOW findings that are not addressed must be listed in a final "Deferred" section with the reason.
- Every test ID from Phase 4 must appear in at least one step's "Implements tests."
- No step touches more than ~15 files or ~500 lines unless it is a pure mechanical move verified by characterization tests (state when this exception applies).
- No step changes behavior and moves code at the same time. Moves are proven by characterization tests; behavior changes are proven by new tests. Separate steps.
- Every step with a database migration includes: the migration file content outline, the down migration, a data-integrity assertion test, and the instruction to back up before applying in production.
- Every step that touches money or auth is marked HIGH risk and includes an additional E2E verification.
- Include an explicit "Stage gate" checkpoint at the end of each stage: a step that only runs the full suite, re-reads this plan, confirms all findings for the stage are resolved, and updates PROGRESS.md with a stage summary.
- Provide a dependency diagram (Mermaid) of the steps so parallelizable steps are visible (though the human will run them sequentially).
- Provide a summary table at the top: step number, title, stage, risk, size, findings resolved.
- Estimate the total number of steps. A well-decomposed plan for a mid-sized app will typically have 60 to 150 steps. If you have fewer than 40, your steps are too large; split them.

## 5.4 The execution protocol (`06-execution-protocol.md`)

Write the exact procedure a future Claude session follows when told "Execute Step N." It must include:

1. **Read**: this protocol, the step, PROGRESS.md, the root CLAUDE.md, and only the files the step lists.
2. **Verify preconditions**: run each check. If any fails, STOP, report which one, and do not proceed.
3. **Create a branch** `refactor/step-NNN-<slug>` from main.
4. **Red**: write every test listed. Run them. Confirm each FAILS for the stated reason. If a test passes unexpectedly, STOP and report (the step's assumption about current behavior is wrong).
5. **Green**: implement exactly the listed actions. Run the new tests until green. Do not touch files not listed.
6. **Refactor**: apply only the listed cleanups. Run `check`.
7. **Lock-in**: apply the lint/static rule. Run `check`.
8. **Verification**: run every verification command. All must pass. If any fails, fix within the step's scope; if it cannot be fixed within scope, revert all changes (`git checkout -- . && git clean -fd` on the branch) and report exactly what failed and why.
9. **Scope check**: `git diff --stat main` and confirm only expected files changed. If unexpected files changed, explain each or revert.
10. **Commit** with the specified message. Merge to main (fast-forward or squash per repo convention). Push.
11. **Update PROGRESS.md**: step number, commit hash, date, test counts before/after, any deviations from the plan and why.
12. **Report** to the human: a five-line summary (what changed, tests added, check status, anything surprising, next step number).
13. **Never**: skip the red phase; disable or delete a test to get green; widen the step; start the next step in the same session unless told to; apply a migration to production (only local/test; production migrations are applied by the deploy process after merge, and the step must say so).

Also include a section "If something goes wrong," with the exact recovery procedure for: a precondition failing, a red test passing, a green phase that cannot be reached within scope, an unrelated test breaking, a merge conflict, and a context reset mid-step (how to detect what was done from git status and PROGRESS.md and resume or revert).

## 5.5 Phase 5 self-check

- [ ] Every CRITICAL/HIGH finding is in a step; every unaddressed finding is in "Deferred" with a reason.
- [ ] Every Phase 4 test ID is in a step.
- [ ] Every step follows the template with no empty fields.
- [ ] No step both moves code and changes behavior.
- [ ] Every migration step has a down migration and backup instruction.
- [ ] Stage gates exist.
- [ ] Step count is at least 40, or you have justified in writing why fewer suffice.
- [ ] `06-execution-protocol.md` is complete including the recovery section.

---

# PHASE 6: HARNESS DRAFTS

**Output:** `docs/refactor/harness-drafts/` (these are drafts; plan steps in Stages 0 and 6 copy them into place)

Produce complete, ready-to-use file contents (not outlines) for:

- `harness-drafts/CLAUDE.stage0.md`: the interim CLAUDE.md for the current structure (used from Stage 0).
- `harness-drafts/CLAUDE.final.md`: the final CLAUDE.md for the target structure (applied in Stage 6).
- `harness-drafts/skills/<name>/SKILL.md` for every skill in 3.2 and 3.4. Each skill is a complete procedure with: frontmatter (`name`, `description` stating when to use it), files to read first, numbered steps, tests to write, verification command, definition of done, and common mistakes to avoid. Written for the TARGET architecture.
- `harness-drafts/module-README.template.md`.
- `harness-drafts/scripts/`: every script from 3.4, executable as written for the real stack.
- `harness-drafts/eslint.config.*` (or the stack's equivalent): the full lint config including boundary rules and size budgets.
- `harness-drafts/.dependency-cruiser.*` if used.
- `harness-drafts/ci/<workflow>.yml`: the full CI workflow.
- `harness-drafts/pre-commit`: hook config.
- `harness-drafts/vitest.config.*` (or equivalent) and `playwright.config.*`.
- `harness-drafts/adr/0001-*.md` through `000N-*.md` from 3.6.
- `harness-drafts/.env.example` with every variable and a one-line description, no values.
- `harness-drafts/test-utils/`: factory file skeletons, fake repository skeletons, test DB lifecycle helper, MSW handler skeletons for each external service.

Every draft must be specific to the real stack. Do not leave placeholder text such as `<your-framework>`; fill in the real values from Phase 0.

## 6.1 Phase 6 self-check

- [ ] Every file listed above exists with complete contents.
- [ ] No placeholder tokens remain (search the folder for `<`, `TODO`, `TBD`, `XXX`).
- [ ] Each skill is under 120 lines and `CLAUDE.final.md` is under 150 lines.

---

# PHASE 7: EXECUTIVE SUMMARY

**Output:** `docs/refactor/README.md`

Written for the non-developer owner. Plain language, no jargon without a parenthetical explanation. Contents:

1. **What was examined**: size of the codebase, stack, in two sentences.
2. **The verdict on the hypothesis**: does the codebase have a thin harness, fat skills, and isolated modules? One sentence each with the key evidence in plain words.
3. **Top 10 problems** ranked by how much they contribute to slow edits, cost, misapplied changes, and regressions. Each: one plain sentence on what it is, one on why it causes the symptom, one on what the fix is.
4. **Security and money findings** that need attention soonest (plain language, no secret values).
5. **Test coverage today vs. target**: a short table.
6. **Expected improvement**: the before/after context-cost table from 3.5, explained in one paragraph.
7. **The plan at a glance**: number of steps, the six stages, what the site can and cannot do during the refactor (it keeps working throughout), and the recommended cadence (e.g., run 3 to 5 steps per evening session).
8. **How to run a step**: the exact command from Part A.3.
9. **Risks and how they are handled**: migrations, money handling, third-party integrations.
10. **Open questions** for the owner (from `OPEN-QUESTIONS.md`), each with the assumption that was made so the plan can proceed without an answer.
11. **File index**: what each file in `docs/refactor/` contains and who should read it.

---

# PART C: QUALITY BAR AND FINAL REVIEW

Before declaring the brief complete, re-read every output file against these criteria and fix every violation:

**Precision**
- Every code reference is `path:line` or `path:line-line`.
- Every number comes from a recorded command.
- Every fix names target files and symbols.

**Completeness**
- Lists are exhaustive. Search each report for "e.g.," "such as," "for example," "etc.," "and more," "among others," "various," "several," "some," "many." Each occurrence must either be replaced with the full list or justified by a reference to an appendix with the full list.
- Every category, every route, every endpoint, every table, every critical path is covered.

**Actionability**
- Search for "consider," "should probably," "might want to," "could," "ideally," "as appropriate," "as needed," "TBD," "TODO." Replace every occurrence with a decision.
- Every plan step could be executed by someone who has read only that step, the protocol, and the files it lists.

**Safety**
- No step breaks the site. Every behavior change has a test first. Every move has a characterization test. Every migration has a rollback.
- No secret value appears anywhere in `docs/refactor/`.
- Money and auth steps are marked HIGH risk and carry E2E verification.

**Stack fidelity**
- Every tool, library, and command named exists for the real stack and real versions found in Phase 0.

**Resumability**
- `PROGRESS.md` shows every phase complete with its output file.
- `OPEN-QUESTIONS.md` lists every assumption made.

Finish by printing to the human: the path to `docs/refactor/README.md`, the total number of findings by severity, the number of planned tests, the number of plan steps, and the single command to run Step 1.
