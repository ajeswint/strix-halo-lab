#!/usr/bin/env bash
# Install etc/sudoers.d/llmctl as /etc/sudoers.d/llmctl (root:root 0440). Run once, by the user,
# from a terminal (it needs your sudo password):
#   /home/aj/projects/strix-halo-lab/scripts/install-llmctl-sudoers.sh
# Safe to rerun: an identical installed file is left alone; a different one is never overwritten.
# Last line, and exit status:
#   OK ... (exit 0)         installed, and `sudo -n systemctl stop llama-deepseek` ran without a password
#   UNVERIFIED ... (exit 2) installed, but llama-deepseek is active so the passwordless check was not run
#   FAIL ... (exit 1)       the reason follows FAIL
# Why not `sudo -n -l <command>`: sudo -l only asks whether the command is permitted, and with the default
# listpw=any it needs no password once ANY rule is NOPASSWD, so it passes for commands the drop-in does not
# list. The check here runs the real stop command, which is a no-op while the unit is inactive. start is on the
# same rule line as stop, so it carries the same NOPASSWD tag.
set -u
src=$(cd "$(dirname "$0")/.." && pwd)/etc/sudoers.d/llmctl
dst=/etc/sudoers.d/llmctl
fail() { echo "FAIL: $*"; exit 1; }

[ -f "$src" ] || fail "missing $src"
sudo -v || fail "sudo authentication failed (wrong password, or no terminal: run this in a terminal, not through an agent)"
out=$(sudo visudo -cf "$src" 2>&1) || fail "visudo rejects $src: $out"
if sudo test -e "$dst"; then
    sudo cmp -s "$src" "$dst" || fail "$dst exists and differs from $src; compare with: sudo diff $src $dst"
else
    sudo install -o root -g root -m 0440 "$src" "$dst" || fail "install into $dst"
fi
out=$(sudo visudo -cf "$dst" 2>&1) || fail "visudo rejects the installed $dst: $out"

if systemctl is-active -q llama-deepseek; then
    echo "UNVERIFIED: $dst installed, but llama-deepseek is active, so the passwordless check (which runs systemctl stop) was skipped. Rerun this script when it is inactive."
    exit 2
fi
sudo -k
out=$(sudo -n /usr/bin/systemctl stop llama-deepseek 2>&1) \
    || fail "$dst is installed but sudo still wants a password for: systemctl stop llama-deepseek ($out). Another sudoers rule may match later and override it"
echo "OK: $dst installed; sudo -n ran systemctl stop llama-deepseek (a no-op, the unit was inactive) without a password; start shares that rule line"
