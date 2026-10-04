#!/usr/bin/env bash
# ROCm 10.0.0 for gfx1151 on Ubuntu 26.04 (inbox amdgpu driver, no dkms)
set -euo pipefail

mkdir --parents --mode=0755 /etc/apt/keyrings
curl -fsSL https://stable.repo.amd.com/rocm/gpg/packages.gpg | gpg --dearmor --yes -o /etc/apt/keyrings/amdrocm.gpg

cat > /etc/apt/sources.list.d/amdrocm-stable.sources << 'EOF'
X-Repo-Id: amdrocm-stable
Types: deb
URIs: https://stable.repo.amd.com/rocm/core/packages/ubuntu2604/
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/amdrocm.gpg
Enabled: yes
EOF

apt-get update

# Gate: the dry run must not pull rocminfo/amd-smi/hip from the Ubuntu archive
plan=$(apt-get install -s amdrocm-core-dev10.0-gfx1151)
echo "$plan" | grep '^Inst' | grep -Ei 'amd-smi|rocm|hip' | grep -i 'ubuntu' && {
  echo "ABORT: Ubuntu-archive ROCm packages would be installed; see above" >&2; exit 1; } || true
echo "$plan" | grep -c '^Inst' | xargs echo "packages to install:"

apt-get install -y amdrocm-core-dev10.0-gfx1151
usermod -a -G render,video aj

echo
echo "Done. Log out and back in (or reboot), then run: bash ~/projects/rocm-verify.sh"
