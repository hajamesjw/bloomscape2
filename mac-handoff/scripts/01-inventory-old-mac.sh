#!/usr/bin/env bash
# =============================================================================
# 01-inventory-old-mac.sh  —  RUN ON THE OLD MAC (the "ops" Mac)
#
# Writes a secrets-free inventory of everything Claude on this Mac is wired to,
# so the new Mac's Claude can recreate it. Output goes into the shared
# workspace (default) so the new Mac can read it the moment sync finishes.
#
#   OUT="$HOME/Claude/_handoff/ops-mac" bash 01-inventory-old-mac.sh
#
# Nothing here prints token values. Where a secret lives, it prints WHERE
# (file + key name, or Keychain item name), never the value.
# =============================================================================
set -uo pipefail

OUT="${OUT:-$HOME/Claude/_handoff/$(scutil --get ComputerName 2>/dev/null | tr ' ' '-' || hostname -s)}"
mkdir -p "$OUT"
R="$OUT/INVENTORY.md"
redact() { # mask anything that looks like a token/key/password value
  sed -E 's/("?(api[_-]?key|token|secret|password|authorization|bearer|cookie|key)"?[[:space:]]*[:=][[:space:]]*"?)[^",}[:space:]]{6,}/\1«REDACTED»/Ig' \
  | sed -E 's/(sk-ant-|sk-|ghp_|gho_|xox[baprs]-|npg_|eyJ)[A-Za-z0-9_\-\.]{8,}/\1«REDACTED»/g'
}
section() { printf '\n## %s\n\n' "$1" >> "$R"; }
code()    { printf '```%s\n' "${1:-}" >> "$R"; cat >> "$R"; printf '```\n' >> "$R"; }

{
  echo "# Handoff inventory — $(scutil --get ComputerName 2>/dev/null) ($(hostname -s))"
  echo
  echo "- Generated: $(date -Iseconds)"
  echo "- macOS: $(sw_vers -productVersion) ($(uname -m))"
  echo "- User: $USER   Home: $HOME"
  echo "- Role: **ops Mac** — runs scheduled/daily routines and inbox triage"
} > "$R"

section "Claude Code"
{
  echo "claude: $(command -v claude || echo 'not on PATH')"
  claude --version 2>/dev/null || true
  echo; echo "# claude doctor (may prompt; skipped if non-interactive)"
  echo; echo "# auth status"
  claude auth status 2>/dev/null || echo "(claude auth status unavailable — run 'claude' and /status manually)"
} | redact | code text

section "Claude Code — user settings (~/.claude/settings.json)"
[[ -f "$HOME/.claude/settings.json" ]] && redact < "$HOME/.claude/settings.json" | code json || echo "_none_" >> "$R"
cp "$HOME/.claude/settings.json" "$OUT/settings.json" 2>/dev/null && redact < "$OUT/settings.json" > "$OUT/settings.json.tmp" && mv "$OUT/settings.json.tmp" "$OUT/settings.json"

section "Claude Code — MCP servers (all scopes)"
{ claude mcp list 2>/dev/null || echo "(claude mcp list failed)"; } | redact | code text
# Per-server config (user scope lives in ~/.claude.json; print command/args/url but redact env values)
if [[ -f "$HOME/.claude.json" ]] && command -v python3 >/dev/null; then
  python3 - "$HOME/.claude.json" <<'PY' | code json
import json,sys,re
d=json.load(open(sys.argv[1]))
def red(o):
    if isinstance(o,dict):
        return {k:("«REDACTED»" if re.search(r'key|token|secret|pass|auth|cookie',k,re.I) and isinstance(v,str) else red(v)) for k,v in o.items()}
    if isinstance(o,list): return [red(x) for x in o]
    return o
out={"userScopeMcpServers":red(d.get("mcpServers",{})),
     "projects":{p:{"mcpServers":red(v.get("mcpServers",{})),"allowedTools":v.get("allowedTools"),"hasTrustDialogAccepted":v.get("hasTrustDialogAccepted")} for p,v in d.get("projects",{}).items()},
     "oauthAccount":{k:v for k,v in d.get("oauthAccount",{}).items() if k in("emailAddress","organizationName","accountUuid")}}
print(json.dumps(out,indent=2))
PY
fi
# Project-scoped .mcp.json files anywhere under home (shallow)
find "$HOME" -maxdepth 5 -name .mcp.json -not -path '*/node_modules/*' 2>/dev/null | while read -r f; do
  echo "### $f" >> "$R"; redact < "$f" | code json
done

section "Claude Code — portable customisations"
{
  for d in CLAUDE.md skills agents commands rules hooks plugins/installed_plugins.json keybindings.json; do
    p="$HOME/.claude/$d"
    if [[ -e "$p" ]]; then echo "✔ ~/.claude/$d"; [[ -d "$p" ]] && find "$p" -maxdepth 2 -not -name '.*' | sed 's|^|    |'; else echo "✘ ~/.claude/$d (absent)"; fi
  done
  echo
  echo "# auto-memory / project memory dirs"
  find "$HOME/.claude/projects" -maxdepth 2 -type d -name memory 2>/dev/null | sed 's|^|    |'
} | code text
# Copy the portable bits (never projects/ transcripts, never credentials)
for d in CLAUDE.md skills agents commands rules hooks keybindings.json; do
  [[ -e "$HOME/.claude/$d" ]] && cp -R "$HOME/.claude/$d" "$OUT/dot-claude-$d" 2>/dev/null
done
find "$HOME/.claude/projects" -maxdepth 2 -type d -name memory 2>/dev/null | while read -r m; do
  proj="$(basename "$(dirname "$m")")"; mkdir -p "$OUT/memory/$proj"; cp -R "$m/." "$OUT/memory/$proj/" 2>/dev/null
done

section "Claude Desktop app (Cowork) — local MCP config"
CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [[ -f "$CFG" ]]; then redact < "$CFG" | code json; else echo "_no claude_desktop_config.json (connectors are account-level on claude.ai and need nothing here)_" >> "$R"; fi
ls "$HOME/Library/Application Support/Claude/" 2>/dev/null | sed 's|^|    |' | code text

section "Where the secrets live (names only — re-enter these on the new Mac)"
{
  echo "# macOS Keychain items that look Claude/dev related (names only):"
  security dump-keychain 2>/dev/null | grep -E '"svce"|"acct"' | grep -iE 'claude|anthropic|github|neon|steady|slack|google|openai|mcp' | sort -u | sed 's/^ *//' | head -60
  echo
  echo "# Env vars set in shell rc files (names only):"
  grep -hoE '^\s*export\s+[A-Z0-9_]+' "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.bashrc" "$HOME/.bash_profile" "$HOME/.zshenv" 2>/dev/null | awk '{print $2}' | sort -u
  echo
  echo "# .env files under the Claude folder (paths only):"
  find "$HOME/Documents/Claude" "$HOME/Claude" -maxdepth 5 -name '.env*' -not -path '*/node_modules/*' 2>/dev/null
  echo
  echo "# 1Password CLI: $(command -v op >/dev/null && op --version || echo 'not installed')"
} | code text

section "Dev toolchain to mirror"
{
  for t in brew git gh node npm pnpm bun uv python3 docker op psql neonctl vercel; do
    printf '%-9s %s\n' "$t" "$(command -v $t >/dev/null && $t --version 2>/dev/null | head -1 || echo '—')"
  done
  echo; echo "# git identity"; git config --global user.name; git config --global user.email
  echo; echo "# SSH keys (public names only)"; ls "$HOME/.ssh"/*.pub 2>/dev/null
  echo; echo "# gh auth"; gh auth status 2>&1 | redact | head -8
} | code text
command -v brew >/dev/null && brew bundle dump --file="$OUT/Brewfile" --force --describe 2>/dev/null && echo "- Brewfile written: $OUT/Brewfile" >> "$R"

section "Scheduled work on this Mac (keep running here — this is the ops Mac)"
{
  echo "# user launchd agents"; ls "$HOME/Library/LaunchAgents" 2>/dev/null
  echo; echo "# crontab"; crontab -l 2>/dev/null || echo "(none)"
  echo; echo "# claude.ai scheduled tasks / routines are account-level: list them in the app and paste here."
} | code text

section "Existing Claude folder — shape (top 3 levels)"
SRC="${SRC:-$HOME/Documents/Claude}"
if [[ -d "$SRC" ]]; then
  { echo "$SRC  ($(du -sh "$SRC" | cut -f1))"; find "$SRC" -maxdepth 3 -type d -not -path '*/node_modules*' -not -path '*/.git*' | sed "s|$SRC|.|" | sort; } | code text
  echo "### CLAUDE.md files found" >> "$R"
  find "$SRC" -maxdepth 4 -iname 'CLAUDE.md' -not -path '*/node_modules/*' | sed "s|$SRC|.|" | code text
  echo "### git repos inside the folder (these should move to ~/Code and sync via GitHub, not the cloud)" >> "$R"
  find "$SRC" -maxdepth 4 -type d -name .git | sed "s|$SRC|.|;s|/.git$||" | code text
else
  echo "_Claude folder not found at $SRC — set SRC=…_" >> "$R"
fi

echo
echo "Inventory written to: $OUT"
echo "  $R"
echo
echo "Review it once for anything sensitive (grep -i key), then it is safe to leave in the shared workspace."
