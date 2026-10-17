# _inbox — per-machine drop zones

Each Mac writes ONLY to its own subfolder. That makes simultaneous work safe: two
machines never touch the same file.

- `ops-mac/`    — written by the old Mac (outputs of scheduled routines, reports, captured notes)
- `studio-mac/` — written by the new Mac (new ideas, drafts, things to file)

The **studio-mac** (primary) triage (`/triage-inbox`, see `_claude/commands/triage-inbox.md`)
reads BOTH inboxes, decides how each item folds into `Companies/<Company>/…`, moves it there,
and leaves a record in `_inbox/<machine>/_filed/YYYY-MM-DD/FILED.md` so the other machine
can see what happened. Run it whenever you start work on studio-mac, or on a schedule there.
