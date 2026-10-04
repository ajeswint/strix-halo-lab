#!/usr/bin/env bash
# Partition + format WD_BLACK SN7100X 2TB (serial 254445804926) as XFS, mount at /data.
# Run with: sudo bash ~/projects/data-drive-setup.sh
set -euo pipefail

DEV=/dev/disk/by-id/nvme-WD_BLACK_SN7100X_2TB_254445804926
PART=${DEV}-part1
MNT=/data
OWNER=aj

[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
command -v mkfs.xfs >/dev/null || { echo "xfsprogs missing: apt install xfsprogs"; exit 1; }
[[ -b $DEV ]] || { echo "$DEV not found"; exit 1; }

REAL=$(readlink -f "$DEV")
ROOTDISK=$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")
[[ $(basename "$REAL") != "$ROOTDISK" ]] || { echo "ABORT: $REAL is the root disk"; exit 1; }
[[ $(lsblk -dno SERIAL "$REAL") == 254445804926 ]] || { echo "ABORT: serial mismatch"; exit 1; }
[[ -z $(lsblk -no MOUNTPOINTS "$REAL" | tr -d '[:space:]') ]] || { echo "ABORT: something on $REAL is mounted"; exit 1; }
[[ $(lsblk -no NAME "$REAL" | wc -l) -eq 1 ]] || { echo "ABORT: $REAL already has partitions"; exit 1; }
[[ -z $(wipefs -n "$REAL") ]] || { echo "ABORT: existing signatures on $REAL:"; wipefs -n "$REAL"; exit 1; }
grep -qE "[[:space:]]$MNT[[:space:]]" /etc/fstab && { echo "ABORT: $MNT already in fstab"; exit 1; }

echo "Target: $REAL ($(lsblk -dno MODEL,SIZE "$REAL"))"
read -r -p "Type YES to partition and format: " ok
[[ $ok == YES ]] || { echo "aborted"; exit 1; }

sgdisk --zap-all "$REAL"
sgdisk -n 1:1MiB:0 -t 1:8300 -c 1:data "$REAL"
partprobe "$REAL"
udevadm settle
[[ -b $PART ]] || { echo "partition node $PART missing"; exit 1; }

mkfs.xfs -L data "$PART"
udevadm settle
UUID=$(blkid -s UUID -o value "$PART")
[[ -n $UUID ]] || { echo "no UUID"; exit 1; }

cp -a /etc/fstab /etc/fstab.bak-$(date +%Y%m%d-%H%M%S)
printf '# %s: WD_BLACK SN7100X 2TB data drive\nUUID=%s %s xfs defaults,nofail 0 2\n' "$MNT" "$UUID" "$MNT" >> /etc/fstab

mkdir -p "$MNT"
systemctl daemon-reload
mount "$MNT"
chown "$OWNER:$OWNER" "$MNT"
install -d -o "$OWNER" -g "$OWNER" "$MNT"/{models,datasets,hf-cache,checkpoints,scratch}

echo
findmnt "$MNT"
xfs_info "$MNT" | grep -E 'reflink|bsize=|crc'
df -h "$MNT"
ls -l "$MNT"
