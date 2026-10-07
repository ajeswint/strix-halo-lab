#!/usr/bin/env bash
# Install etc/sudoers.d/llmctl as /etc/sudoers.d/llmctl (root:root 0440). Run once, by the user:
#   scripts/install-llmctl-sudoers.sh
# It validates the file with visudo before installing, refuses to overwrite a different existing file,
# then drops sudo's cached credentials and checks that the two commands now pass without a password.
# Prints OK or FAIL on the last line.
set -u
src=$(cd "$(dirname "$0")/.." && pwd)/etc/sudoers.d/llmctl
dst=/etc/sudoers.d/llmctl
fail() { echo "FAIL: $*"; exit 1; }

[ -f "$src" ] || fail "missing $src"
sudo visudo -cf "$src" >/dev/null || fail "visudo rejects $src"
if sudo test -e "$dst"; then
    sudo cmp -s "$src" "$dst" || fail "$dst exists and differs from $src; compare with: sudo diff $src $dst"
else
    sudo install -o root -g root -m 0440 "$src" "$dst" || fail "install into $dst"
fi
sudo visudo -cf "$dst" >/dev/null || fail "visudo rejects the installed $dst"
sudo -k
for verb in start stop; do
    sudo -n -l /usr/bin/systemctl "$verb" llama-deepseek >/dev/null 2>&1 || fail "sudo -n still asks for a password for: systemctl $verb llama-deepseek"
done
echo "OK: $dst installed; sudo -n allows systemctl start|stop llama-deepseek (nothing was started or stopped)"
