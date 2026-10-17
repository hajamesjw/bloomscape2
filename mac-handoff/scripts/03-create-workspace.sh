#!/usr/bin/env bash
# =============================================================================
# 03-create-workspace.sh  —  RUN ON BOTH MACS (idempotent)
#
# Creates / adopts the shared Claude workspace inside your cloud-synced folder,
# links it to ~/Claude, tags this machine with its role, and wires the shared
# _claude/ customisations into ~/.claude.
#
#   MACHINE=ops-mac    bash 03-create-workspace.sh          # on the old Mac
#   MACHINE=studio-mac bash 03-create-workspace.sh          # on the new Mac
#
# Optional:
#   CLOUD_ROOT="…"   where the synced folder lives (auto-detected: iCloud → Google Drive → Dropbox)
#   TEMPLATE="…"     path to workspace-template (default: ../workspace-template next to this script)
# =============================================================================
set -euo pipefail

MACHINE="${MACHINE:?Set MACHINE=ops-mac or MACHINE=studio-mac}"
[[ "$MACHINE" == "ops-mac" || "$MACHINE" == "studio-mac" ]] || { echo "MACHINE must be ops-mac or studio-mac"; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="${TEMPLATE:-$HERE/../workspace-template}"

detect_cloud() {
  if [[ -n "${CLOUD_ROOT:-}" ]]; then echo "$CLOUD_ROOT"; return; fi
  local db; db="$(ls -d "$HOME"/Library/CloudStorage/Dropbox* "$HOME/Dropbox" 2>/dev/null | head -1 || true)"
  [[ -n "$db" ]] && { echo "$db"; return; }
  local ic="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
  [[ -d "$ic" ]] && { echo "$ic"; return; }
  local gd; gd="$(ls -d "$HOME"/Library/CloudStorage/GoogleDrive-*/My\ Drive 2>/dev/null | head -1 || true)"
  [[ -n "$gd" ]] && { echo "$gd"; return; }
  echo ""
}
CLOUD_ROOT="$(detect_cloud)"
[[ -n "$CLOUD_ROOT" && -d "$CLOUD_ROOT" ]] || { echo "No cloud folder found. Set CLOUD_ROOT=/path/to/synced/folder"; exit 1; }
WS="$CLOUD_ROOT/Claude"

echo "Machine   : $MACHINE"
echo "Cloud root: $CLOUD_ROOT"
echo "Workspace : $WS   (→ ~/Claude)"
echo

# 1) Create or adopt the workspace folder from the template (never overwrite existing files)
mkdir -p "$WS"
if command -v rsync >/dev/null; then
  rsync -a --ignore-existing --exclude '.DS_Store' "$TEMPLATE"/ "$WS"/
else
  cp -Rn "$TEMPLATE"/. "$WS"/ 2>/dev/null || true
fi
mkdir -p "$WS/_inbox/$MACHINE/_filed" "$WS/_handoff/$MACHINE"

# 2) ~/Claude → workspace (symlink; replace a stale link, refuse to clobber a real folder)
if [[ -L "$HOME/Claude" ]]; then ln -sfn "$WS" "$HOME/Claude"
elif [[ -e "$HOME/Claude" ]]; then echo "WARN: ~/Claude exists and is not a symlink; leaving it. Move it aside and re-run to link."
else ln -s "$WS" "$HOME/Claude"; fi

# 3) Machine tag (read by CLAUDE.md rules: `cat ~/.claude-machine`)
echo "$MACHINE" > "$HOME/.claude-machine"

# 4) Keep the whole workspace downloaded on this machine (per-provider)
case "$CLOUD_ROOT" in
  *"Mobile Documents"*)
    echo "iCloud: pinning workspace as always-downloaded…"
    # Finder → right-click folder → "Keep Downloaded" is the durable setting; brctl forces the download now.
    brctl download "$WS" >/dev/null 2>&1 || true
    echo "  → Also: System Settings → Apple Account → iCloud → Drive → turn OFF 'Optimize Mac Storage' (both Macs)." ;;
  *GoogleDrive*)
    echo "Google Drive: set the 'Claude' folder to 'Available offline' (Finder → right-click → Offline access), or switch Drive to Mirror mode." ;;
  *Dropbox*)
    echo "Dropbox: Finder → right-click 'Claude' → 'Make available offline'. Turn OFF Smart Sync/auto-online-only in Dropbox prefs." ;;
esac

# 5) Wire shared customisations into ~/.claude (dirs are symlinked; existing content is merged into the workspace first)
mkdir -p "$HOME/.claude"
for d in skills agents commands rules; do
  src="$WS/_claude/$d"; dst="$HOME/.claude/$d"; mkdir -p "$src"
  if [[ -L "$dst" ]]; then ln -sfn "$src" "$dst"
  elif [[ -d "$dst" ]]; then
    if command -v rsync >/dev/null; then rsync -a --ignore-existing "$dst"/ "$src"/; else cp -Rn "$dst"/. "$src"/ 2>/dev/null || true; fi
    mv "$dst" "$dst.pre-workspace.bak"; ln -s "$src" "$dst"
  else ln -s "$src" "$dst"; fi
done
# settings.json: shared file is COPIED (not linked) the first time so a sync hiccup can never break Claude Code mid-session.
if [[ ! -f "$HOME/.claude/settings.json" ]]; then cp "$WS/_claude/settings.json" "$HOME/.claude/settings.json"; echo "Installed ~/.claude/settings.json from workspace."
else echo "Kept existing ~/.claude/settings.json. Diff against the shared one with:  diff ~/.claude/settings.json ~/Claude/_claude/settings.json"; fi
# Workspace rules are imported by the user-level CLAUDE.md so they apply even outside ~/Claude
touch "$HOME/.claude/CLAUDE.md"
grep -q '_claude/rules/sync-safety.md' "$HOME/.claude/CLAUDE.md" || printf '\n# Shared workspace rules\n@~/Claude/_claude/rules/sync-safety.md\n' >> "$HOME/.claude/CLAUDE.md"

# 6) Sync-ignore guards: make sure heavy dirs never sync even if someone slips
cat > "$WS/.syncignore-NOTE.md" <<'N'
Nothing under this workspace should ever contain .git, node_modules, .venv, dist or build.
If it happens anyway, exclude it from sync immediately:
  Dropbox : xattr -w com.dropbox.ignored 1 <path>
  iCloud  : rename to <name>.nosync (iCloud skips *.nosync) and symlink the original name to it
  GDrive  : no per-folder ignore — move it out to ~/Code
N

# 7) ~/Code for repos (per machine, synced via GitHub)
mkdir -p "$HOME/Code"

echo
echo "Done. Open a terminal in ~/Claude and run:  claude"
echo "First prompt to try:  'Read CLAUDE.md and _handoff/*/INVENTORY.md and tell me what this machine still needs connected.'"
