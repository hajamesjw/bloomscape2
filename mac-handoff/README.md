# mac-handoff — two-Mac Claude workspace kit

Start with **HANDOFF.md**. Research and sources are in **RESEARCH.md**.

| File | Run on | Purpose |
|------|--------|---------|
| `scripts/00-backup-claude-folder.sh` | old Mac | Dated backup of `~/Documents/Claude` + Claude config into `<cloud>/Backups/` |
| `scripts/01-inventory-old-mac.sh` | old Mac | Secrets-free inventory of MCP servers, settings, Keychain item names, Brewfile → `~/Claude/_handoff/ops-mac/` |
| `scripts/02-bootstrap-new-mac.sh` | new Mac | Install Homebrew, git, node, Claude Code, Claude desktop, gh, 1Password CLI, uv |
| `scripts/03-create-workspace.sh` | both | Create/adopt `<cloud>/Claude`, link `~/Claude`, tag machine role, link shared `_claude/` into `~/.claude` |
| `workspace-template/` | — | The folder layout and CLAUDE.md files the workspace starts from |

Quick start on either Mac:

```bash
git clone https://github.com/hajamesjw/bloomscape2.git ~/Code/bloomscape2
cd ~/Code/bloomscape2 && git checkout claude/relaxed-shannon-61emy1
MACHINE=ops-mac  bash mac-handoff/scripts/03-create-workspace.sh   # old Mac
MACHINE=studio-mac bash mac-handoff/scripts/03-create-workspace.sh # new Mac
```
