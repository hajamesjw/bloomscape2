---
description: File everything in _inbox/* into the right Company/Project folder (ops-mac daily routine)
---
You are running the daily inbox triage in the shared Claude workspace (root CLAUDE.md applies).

1. List every file in `_inbox/*/` except `_filed/` and `README.md`.
2. For each file, decide the destination from its content and name:
   - Clearly about an existing project → `Companies/<Company>/Projects/<Project>/context/` (or `work/` if it's an output)
   - A dated routine output → `Companies/<Company>/Daily/YYYY-MM-DD/`
   - A new idea with no project → create `Companies/<Company>/Projects/<slug>/` from `_templates/project/`, set Owner to the machine that wrote the inbox item, and move the file into `context/`
   - Can't tell the company → leave it, list it under "Needs a human" in the report
3. Move (don't copy) each filed item; then write a one-line entry per item to `_inbox/<machine>/_filed/YYYY-MM-DD/FILED.md` (`moved <from> → <to>`).
4. Append a dated block to each touched project's `LOG.md`.
5. Finish with a short report: filed N items, created M projects, K need a human — and list the K.

Never delete anything. Never edit files inside a project whose `Owner:` is the other machine except to append to `LOG.md`.
