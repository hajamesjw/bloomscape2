# Handoff: two-Mac Claude setup

_Written 2026-10-17 from a Claude cloud session (claude.ai account hajamesjw@gmail.com). Read this on the **new Mac** first; the old Mac keeps running._

## 0. The decision in one paragraph

Two Macs share **one cloud-synced folder, `~/Claude`**, fully downloaded on both. The **new Mac is `studio-mac` and is primary**: new projects, creative work, and ownership of the folder structure, including the inbox triage that decides how new material folds in. The **old Mac is `ops-mac`**: it runs scheduled and repeat processes (daily routines, reports, captures) and only *produces* into its own inbox and dated `Daily/` folders; it never reorganises. Both can run at the same time without colliding because the folder is laid out so each machine writes to its own places (per-machine `_inbox/`, per-project `Owner:` field, dated append-only outputs), and because **code never lives in the synced folder**: repos go in `~/Code` on each machine and sync through GitHub. Claude Code's shared customisations (skills, agents, commands, rules) live in the workspace at `_claude/` and are symlinked into `~/.claude` on both machines; everything else in `~/.claude` (sessions, auth, caches) stays per machine.

## 1. What transfers automatically vs. what you must redo

### Follows your claude.ai login (nothing to do on the new Mac)
These are **account-level connectors on claude.ai**, confirmed live on this account today:

| Connector | Status today |
|-----------|--------------|
| Gmail | connected |
| Google Calendar | connected |
| Google Drive | connected |
| Granola | connected |
| Slack | connected |
| GitHub (Claude GitHub App) | installed; repo scope currently `hajamesjw/bloomscape2` |

Also account-level: claude.ai Skills (docs, google-workspace, computer-use, chrome-browser, built-in-browser, deep-research, import-memory, morning, skill-creator, xlsx, pptx, pdf, docx), scheduled tasks created on claude.ai / Claude Code web, Claude Docs, Projects, memory on claude.ai.

### Lives on the old Mac only — must be inventoried and recreated
- **Claude Code MCP servers** in `~/.claude.json` (user scope) and any project `.mcp.json`. This is where **Neon** and **Steady** almost certainly live (they are not among the claude.ai connectors above). Their API keys are in env values inside that file or in Keychain.
- **Claude desktop app (Cowork) local MCP config** at `~/Library/Application Support/Claude/claude_desktop_config.json`, if any.
- **Claude Code auth** (Keychain item) — just run `claude` and log in again on the new Mac.
- **`~/.claude/settings.json`, `CLAUDE.md`, skills, agents, commands, rules, auto-memory** — the inventory script copies these into the workspace.
- **macOS permissions** granted to Terminal / Claude app (Full Disk Access, Files & Folders, Accessibility, Screen Recording, Automation) — re-grant on the new Mac. Section 5.
- Shell dotfiles, git identity, SSH keys, Homebrew packages, `gh` login, 1Password CLI.

**→ Run `scripts/01-inventory-old-mac.sh` on the old Mac.** It writes a secrets-free `INVENTORY.md` into `~/Claude/_handoff/ops-mac/` with every MCP server (command/URL, redacted env), every Keychain item name that looks relevant, env var names, `Brewfile`, launchd/cron jobs, and a map of the existing Claude folder. The new Mac's Claude reads that file and knows exactly what to reconnect.

## 2. Observed state (from this cloud session)

- Google Drive already has a Drive-native workspace: `_Project_Workspace/Projects/{QA, Payroll, PAuths, Billing}` and `_Project_Workspace/_archive/…`, plus `ABC build — James only (do not share)/{Daily, Status, archive, spreadsheets}` owned by `james@abccareteam.com`. Those are Google Docs/Sheets outputs and stay in Drive; the new `~/Claude` workspace should link to them from the company `CLAUDE.md`, not duplicate them.
- Granola has one folder: `ScaleRCM-Axented Daily Meeting` (20 notes).
- Likely companies to create under `Companies/`: **ABC Care Team**, **ScaleRCM / Axented**, **Bloomscape**. Rename freely; these are guesses from Drive and Granola.
- The GitHub repo `hajamesjw/bloomscape2` is empty apart from a README; this kit is pushed to its branch `claude/relaxed-shannon-61emy1`.

## 3. Order of operations

**On the old Mac (ops-mac), today:**
1. `bash mac-handoff/scripts/00-backup-claude-folder.sh` — dated `.tar.zst` + manifest + Claude-config tarball into `<cloud>/Backups/`, then evict the local copy once uploaded (the script prints the exact Finder step).
2. Install / sign in to the sync client you chose (section 4) on this Mac if it is not already.
3. `MACHINE=ops-mac bash mac-handoff/scripts/03-create-workspace.sh` — creates `<cloud>/Claude` from the template, links `~/Claude`, tags the machine, links `~/.claude/{skills,agents,commands,rules}` into the workspace.
4. `bash mac-handoff/scripts/01-inventory-old-mac.sh` — writes `~/Claude/_handoff/ops-mac/INVENTORY.md`.
5. Move your existing Claude folder's content into the new layout (`Companies/<Company>/Projects/<Project>/…`). Do this with Claude: open a terminal in `~/Claude` and ask it to file `~/Documents/Claude` into the new structure, one company at a time. Move any git repos to `~/Code` and leave a `REPO.md` behind.
6. Set up the scheduled routines that stay here (section 6).

**On the new Mac (studio-mac):**
1. `bash mac-handoff/scripts/02-bootstrap-new-mac.sh` — Homebrew, git, node, Claude Code, Claude desktop, gh, 1Password CLI, uv, and the `Brewfile` from the inventory if present.
2. Install the sync client, sign in, let `Claude/` finish downloading, pin it as always-downloaded.
3. `MACHINE=studio-mac bash mac-handoff/scripts/03-create-workspace.sh`
4. Grant macOS permissions (section 5).
5. `cd ~/Claude && claude`, log in, then: _"Read CLAUDE.md and `_handoff/ops-mac/INVENTORY.md`. For each MCP server listed, give me the `claude mcp add` command; for each secret, tell me which Keychain/1Password item to re-enter."_
6. Re-add MCP servers with `claude mcp add …` (user scope), re-enter keys, test one call each (Neon: list projects; Steady: read-only lookup).
7. Run `/triage-inbox` in `~/Claude` for the first time; from now on this Mac decides where things go.

## 4. Which cloud, and how to keep two machines from colliding
_(research-backed section — see RESEARCH.md for sources)_

RESEARCH_SYNC_PLACEHOLDER

## 5. macOS permissions on the new Mac

RESEARCH_PERMS_PLACEHOLDER

## 6. Scheduled routines on ops-mac, triage on studio-mac

RESEARCH_ROUTINE_PLACEHOLDER

## 7. Secrets policy

- Secrets never go into `~/Claude` (synced). They live in macOS Keychain or 1Password, and are referenced by **name** in `CLAUDE.md` files and `INVENTORY.md`.
- For Claude Code MCP servers that need a key, prefer `claude mcp add -e KEY=value …` (stored per machine in `~/.claude.json`, not synced) or an `apiKeyHelper`/env entry in `~/.claude/settings.local.json` (also not synced).
- The template `_claude/settings.json` denies `Read` of `.env*` and `~/.ssh/**` so a synced session can't leak them by accident.

## 8. Known limits of this handoff

- This session ran in a cloud container, so it could not read the old Mac's disk. The backup and inventory had to be scripts for you to run, not actions I took.
- I could not confirm how Neon and Steady are connected on the old Mac; the inventory will.
- Anything stored only in Claude desktop app chats (not in files) does not transfer; account-level claude.ai memory does.
