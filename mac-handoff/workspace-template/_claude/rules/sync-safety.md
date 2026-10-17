# Sync safety (applies in every folder of the shared workspace)
- Before editing a file, check for a sibling conflicted copy (`*conflicted copy*`, `*-conflict*`, `* 2.*`). If present, reconcile first.
- Never `git init`, `npm install`, `pip install`, or build inside the workspace. Code goes in ~/Code.
- Never write a secret value into any file here; write where it lives instead.
- Only edit projects whose `Owner:` matches `cat ~/.claude-machine`; otherwise leave a note in `_inbox/<your-machine>/`.
