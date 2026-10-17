# <Company> — company context

**What they do:** one paragraph.
**My role:** what I do for them, since when, cadence.
**Primary machine:** ops-mac | studio-mac  (which Mac usually works here)

## People
| Name | Role | How to reach | Notes |
|------|------|--------------|-------|

## Systems & where access lives
| System | What for | Access lives in (never the secret itself) |
|--------|----------|-------------------------------------------|
| e.g. Gmail (james@…) | mail | claude.ai connector (account-level) |
| e.g. Neon (Postgres) | app DB | MCP server `neon` in ~/.claude.json, key in Keychain item `neon-api-key` |
| e.g. Steady | billing | MCP / connector — see `_handoff/<machine>/INVENTORY.md` |

## Standing rules for this company
- Tone / formatting expectations
- Things never to do without asking (send mail, move money, post publicly)
- Data-handling constraints (PHI, PII, contracts)

## Recurring routines (run on ops-mac; outputs land in Daily/YYYY-MM-DD/ or _inbox/ops-mac/)
| Routine | When | Output goes to |
|---------|------|----------------|

## Active projects
See `Projects/*/CLAUDE.md`. Finished → `../../_archive/<Company>/`.
