---
name: live-sync
description: Keep repo copies and the live files they mirror (/etc, /etc/systemd/system, /data/bench, /data/models, /data/envs) identical. Use before committing config changes, after editing any live file, after package upgrades, and at session start or end to catch drift.
---

# Repo copy vs live file

The tree mirrors real paths (CLAUDE.md). A change to either side goes to the other side in the same change.

```
scripts/drift-check.sh
scripts/drift-check.sh -d
```

Exit 0 = no drift. `DRIFT` = contents differ (`-d` shows the diff, repo then live). `UNREADABLE` = root-only file; give the user the `sudo diff` line it prints. `MISSING` = live file gone.

Mapping: `etc/X` -> `/etc/X`; `systemd/X` -> `/etc/systemd/system/X`; `systemd/user/X` -> `~/.config/systemd/user/X` (not installed, by decision; skipped); `bench/`, `models/`, `envs/torch-constraints.txt` -> `/data/...`. `scripts/`, `envs/install-torch-env.sh` and `envs/freeze.txt` run from the repo and have no live copy.

## When drift is found

Find out which side is right before copying anything:
- The live file changed (package upgrade, another agent, a hand edit): check `dpkg -S`, `/var/log/apt/history.log` and mtimes. If the change is unwanted, restoring the live file is a conffile overwrite: ask the user first.
- The repo changed but was never deployed: deploying is a live config change. Ask the user, and give the exact `sudo install` command.
- Never silently "fix" drift in either direction. Report what changed and when.

Known case: Cursor upgrades can replace `/etc/apparmor.d/cursor-sandbox` and drop `capability dac_override,`. The repo copy is the intended state. A second file in that directory which defines `cursor_sandbox` (a `.bak` sorts later and boot reloads it last) has to be moved out first; never copy a backup back into `/etc/apparmor.d/`. Restoring the live file needs the user's yes: `sudo install -m 644 etc/apparmor.d/cursor-sandbox /etc/apparmor.d/cursor-sandbox && sudo apparmor_parser -r /etc/apparmor.d/cursor-sandbox`. Then `grep -n dac_override /etc/apparmor.d/cursor-sandbox` shows the capability, and `test "$(/sbin/apparmor_parser -N /etc/apparmor.d | grep -c '^cursor_sandbox$')" = 1` shows the profile once.

## Adding a mirrored file

Copy it to the matching repo path, add a `case` line in `scripts/drift-check.sh` if it is under a new root, and run the check.
