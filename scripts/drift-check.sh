#!/usr/bin/env bash
# Compare repo copies with the live files they mirror. Read-only.
# Usage: scripts/drift-check.sh [-d]   (-d prints the diff of each drifted file)
# Exit 0 = no drift, 1 = drift or unreadable. Files run from the repo (scripts/,
# envs/install-torch-env.sh, envs/freeze.txt) and not-installed units (systemd/user/) are skipped.
set -u
cd "$(dirname "$0")/.."
showdiff=${1:-}
rc=0
for f in $(git ls-files bench envs etc models systemd); do
    case $f in
        etc/*)          live=/$f ;;
        systemd/user/*) live=$HOME/.config/systemd/user/${f#systemd/user/} ;;
        systemd/*)      live=/etc/systemd/system/${f#systemd/} ;;
        bench/*|models/*|envs/torch-constraints.txt) live=/data/$f ;;
        *) continue ;;
    esac
    if [ ! -e "$live" ]; then
        [[ $f == systemd/user/* ]] && continue   # held by decision (README Orchestrator)
        echo "MISSING    $f -> $live"; rc=1
    elif [ ! -r "$live" ]; then
        echo "UNREADABLE $f -> $live (root-only; compare with: sudo diff $f $live)"; rc=1
    elif ! cmp -s "$f" "$live"; then
        echo "DRIFT      $f -> $live"; rc=1
        [ "$showdiff" = -d ] && diff -u "$f" "$live" | sed 's/^/    /'
    fi
done
[ $rc = 0 ] && echo "no drift"
exit $rc
