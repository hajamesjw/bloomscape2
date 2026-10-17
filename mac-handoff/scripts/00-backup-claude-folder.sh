#!/usr/bin/env bash
# =============================================================================
# 00-backup-claude-folder.sh  —  RUN ON THE OLD MAC FIRST
#
# Makes a dated, compressed backup of your existing Claude folder (and your
# Claude Code / Claude desktop config) into a cloud "Backups" folder, then
# tells the sync client it may evict the local copy so it doesn't eat disk.
#
# Usage:
#   bash 00-backup-claude-folder.sh                       # defaults below
#   SRC="$HOME/Documents/Claude" DEST="$HOME/Library/CloudStorage/GoogleDrive-you@gmail.com/My Drive/Backups" bash 00-backup-claude-folder.sh
#
# Safe: read-only on the source. Creates one .tar.zst (or .tar.gz) + a manifest.
# =============================================================================
set -euo pipefail

SRC="${SRC:-$HOME/Documents/Claude}"
STAMP="$(date +%Y-%m-%d_%H%M)"
HOST="$(scutil --get ComputerName 2>/dev/null | tr ' ' '-' || hostname -s)"

# Pick a backup destination: explicit DEST, else iCloud Drive, else Google Drive, else Dropbox, else ~/Backups
pick_dest() {
  if [[ -n "${DEST:-}" ]]; then echo "$DEST"; return; fi
  local icloud="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
  [[ -d "$icloud" ]] && { echo "$icloud/Backups"; return; }
  local gd; gd="$(ls -d "$HOME"/Library/CloudStorage/GoogleDrive-*/My\ Drive 2>/dev/null | head -1 || true)"
  [[ -n "$gd" ]] && { echo "$gd/Backups"; return; }
  local db; db="$(ls -d "$HOME"/Library/CloudStorage/Dropbox* "$HOME/Dropbox" 2>/dev/null | head -1 || true)"
  [[ -n "$db" ]] && { echo "$db/Backups"; return; }
  echo "$HOME/Backups"
}
DEST="$(pick_dest)"
mkdir -p "$DEST"

[[ -d "$SRC" ]] || { echo "ERROR: source folder not found: $SRC  (set SRC=...)"; exit 1; }

echo "Source : $SRC"
echo "Dest   : $DEST"
echo "Size   : $(du -sh "$SRC" | cut -f1)  (excluding nothing; archive will skip node_modules/.venv/caches)"
echo

ARCHIVE_BASE="$DEST/claude-folder_${HOST}_${STAMP}"
EXCLUDES=(--exclude='node_modules' --exclude='.venv' --exclude='venv' --exclude='__pycache__' \
          --exclude='.next' --exclude='dist' --exclude='build' --exclude='.cache' --exclude='.DS_Store' \
          --exclude='*.icloud')   # *.icloud = evicted placeholders; nothing real to back up there

# 1) Manifest first (so you can grep what was in the backup without extracting)
echo "Writing manifest…"
( cd "$(dirname "$SRC")" && find "$(basename "$SRC")" -type f \
    -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/venv/*' -not -path '*/__pycache__/*' \
    -not -path '*/.next/*' -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/.cache/*' \
    -not -name '.DS_Store' -not -name '*.icloud' \
    -exec stat -f '%z %Sm %N' -t '%Y-%m-%dT%H:%M:%S' {} + ) > "${ARCHIVE_BASE}.manifest.txt"
echo "  $(wc -l < "${ARCHIVE_BASE}.manifest.txt") files listed"

# 2) Archive. zstd is faster/smaller if present; else gzip.
if command -v zstd >/dev/null 2>&1; then
  OUT="${ARCHIVE_BASE}.tar.zst"
  echo "Archiving (zstd) → $OUT"
  tar -c "${EXCLUDES[@]}" -C "$(dirname "$SRC")" "$(basename "$SRC")" | zstd -T0 -3 -q -o "$OUT"
else
  OUT="${ARCHIVE_BASE}.tar.gz"
  echo "Archiving (gzip) → $OUT"
  tar -cz "${EXCLUDES[@]}" -f "$OUT" -C "$(dirname "$SRC")" "$(basename "$SRC")"
fi

# 3) Claude config snapshot (settings, CLAUDE.md, skills, agents, MCP config). NOT the Keychain.
CFG="${ARCHIVE_BASE}_claude-config.tar.gz"
echo "Archiving Claude config → $CFG"
tar -czf "$CFG" -C "$HOME" \
  --exclude='.claude/projects' --exclude='.claude/todos' --exclude='.claude/statsig' \
  --exclude='.claude/shell-snapshots' --exclude='.claude/debug' --exclude='.claude/cache' \
  --exclude='.claude/plugins/cache' --exclude='.claude/plugins/repos' --exclude='.claude/history.jsonl' \
  .claude .claude.json "Library/Application Support/Claude/claude_desktop_config.json" 2>/dev/null || true

# 4) Checksums
( cd "$DEST" && shasum -a 256 "$(basename "$OUT")" "$(basename "$CFG")" > "${ARCHIVE_BASE}.sha256" )

echo
echo "Done:"
ls -lh "${ARCHIVE_BASE}"* | awk '{print "  " $5 "\t" $9}'
echo
echo "Verify once: tar -tf \"$OUT\" | head"
echo
echo "After it has finished uploading (check the sync icon), free local disk:"
case "$DEST" in
  *"Mobile Documents"*) echo "  Finder → right-click '$(basename "$OUT")' → 'Remove Download'   (or: brctl evict \"$OUT\")";;
  *GoogleDrive*)         echo "  Finder → right-click → 'Offline access' → 'Online only'  (Google Drive must be in Stream mode)";;
  *Dropbox*)             echo "  Finder → right-click → 'Make Online-only'";;
  *)                     echo "  (local folder — copy to an external disk or cloud and delete when verified)";;
esac
