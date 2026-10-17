# Claude Workspace — root instructions

You are inside the shared Claude workspace. It is one folder, cloud-synced and fully
downloaded on two Macs that may both be working at the same time:

| Machine     | Role                                                                 | Writes to                         |
|-------------|----------------------------------------------------------------------|-----------------------------------|
| studio-mac  | **primary.** New / creative work, new projects, builds. Owns the folder structure and runs the inbox triage that folds new things in. | `_inbox/studio-mac/`, project folders it owns, anywhere during triage |
| ops-mac     | repeat processes: scheduled routines, reports, captures. Produces; does not reorganise. | `_inbox/ops-mac/`, `Companies/*/Daily/YYYY-MM-DD/`, `LOG.md` appends |

Which machine am I on? Run `cat ~/.claude-machine` (contains `ops-mac` or `studio-mac`).

## Layout

```
Claude/
├─ CLAUDE.md                 ← this file (root rules, applies everywhere below)
├─ _inbox/<machine>/         ← per-machine drop zone. ONLY that machine writes here.
├─ _handoff/<machine>/       ← inventories + handoff docs between machines
├─ _claude/                  ← shared skills / agents / commands / rules (symlinked into ~/.claude)
├─ _templates/               ← scaffolds for new companies / projects
├─ Companies/
│   └─ <Company>/
│       ├─ CLAUDE.md         ← company context: who, systems, credentials *locations*, tone
│       ├─ Reference/        ← stable docs (contracts, SOPs, org charts, exports)
│       ├─ Daily/YYYY-MM-DD/ ← dated outputs of routines (append-only)
│       └─ Projects/
│           └─ <Project>/
│               ├─ CLAUDE.md ← project brief, status, decisions, open questions
│               ├─ context/  ← source material
│               ├─ work/     ← drafts & outputs
│               └─ LOG.md    ← dated running log (append at the bottom)
└─ _archive/                 ← finished things, kept but out of the way
```

## Sync-safety rules (the whole point of the layout)

1. **One writer per folder.** A project folder is "owned" by one machine at a time. Ownership
   is recorded in the project's `CLAUDE.md` under `Owner:`. Don't edit a project the other
   machine owns; drop a note in your `_inbox/<machine>/` instead.
2. **Prefer new dated files over editing shared files.** `Daily/2026-10-17/summary.md`, never
   a single growing `summary.md` edited from both sides. Append-only logs (`LOG.md`) are OK
   because appends from one machine per day don't collide.
3. **No git repos, no node_modules, no build output in this folder.** Code lives in `~/Code/`
   on each machine and syncs through GitHub. A project folder may contain `REPO.md` that says
   which GitHub repo it belongs to. (Cloud sync + `.git` = corrupted repos. See `_handoff/RESEARCH.md`.)
4. **No secrets in this folder.** Say *where* a credential lives (Keychain item, 1Password
   item, env var name). Never paste a key, token, or password into any file here.
5. **If you see a file named `* (conflicted copy)*`, `*-conflict*`, or `* 2.md`**, stop and
   reconcile it by hand before continuing: both versions are kept by the sync client, nothing is lost.
6. **Inbox hygiene.** Anything created without a clear home goes in `_inbox/<machine>/`.
   The **studio-mac** triage (`/triage-inbox`) reads both inboxes, decides where each item belongs,
   files it into Companies/… and clears the inbox. ops-mac never reorganises; it only produces.

## Conventions

- Dates: `YYYY-MM-DD` prefix on files and folders that are time-bound.
- Every project `CLAUDE.md` has: Goal, Owner (machine), Status, Key people, Systems, Next steps.
- When you finish a work session, append 3-6 lines to the project `LOG.md`: what changed, what's next.
- Company-specific rules live in `Companies/<Company>/CLAUDE.md` and override nothing here;
  they add to it.
