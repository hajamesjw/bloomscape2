# _inbox — per-machine drop zones

Each Mac writes ONLY to its own subfolder. That makes simultaneous work safe: two
machines never touch the same file.

- `ops-mac/`    — written by the old Mac (daily routines, reports, captured notes)
- `studio-mac/` — written by the new Mac (new ideas, drafts, things to file)

The ops-mac daily triage routine (see `_claude/commands/triage-inbox.md`) reads BOTH
inboxes, files each item into `Companies/<Company>/…`, and moves the original into
`_inbox/<machine>/_filed/YYYY-MM-DD/` so the other machine can see what happened.
