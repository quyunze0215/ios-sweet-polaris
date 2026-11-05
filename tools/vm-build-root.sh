#!/bin/bash
# Build the iOS 16.7.16 (iPhone X, 20H392) HFS+ root image for the MIX 2S port.
# Run INSIDE the Linux VM (Ubuntu/Debian, needs sudo). Touches no phone.
#
#   sudo apt update && sudo apt install -y apfs-fuse hfsprogs rsync \
#        android-sdk-libsparse-utils unzip python3
#   ./vm-build-root.sh /path/to/iPhone10,3_16.7.16_20H392_Restore.ipsw \
#                      /path/to/ios-sweet /path/to/workdir
#
# Output: <workdir>/ios16-root.simg (+ .sha256)
# Needs ~32 GB free under <workdir>.
#
# NOTE: this firmware's DMGs are NOT named OS.dmg/SystemOS.dmg/AppOS.dmg (the
# upstream docs assume that). Real names are build hashes; we map them by role
# from BuildManifest.plist:
#   OS                -> root filesystem (UDIF)
#   Cryptex1,SystemOS -> System cryptex (raw APFS)
#   Cryptex1,AppOS    -> App cryptex   (raw APFS)
set -euo pipefail

IPSW=${1:?usage: vm-build-root.sh IPSW IOS_SWEET_TREE WORKDIR [SIZE]}
TREE=${2:?}
WORK=${3:?}
SIZE=${4:-16G}

[ -f "$IPSW" ] || { echo "error: no such IPSW: $IPSW" >&2; exit 1; }
[ -d "$TREE/tools" ] || { echo "error: $TREE is not the ios-sweet tree" >&2; exit 1; }
mkdir -p "$WORK"

echo "== checks =="
for t in apfs-fuse mkfs.hfsplus fsck.hfsplus rsync unzip img2simg python3; do
	command -v "$t" >/dev/null || { echo "error: missing $t (apt install apfs-fuse hfsprogs rsync android-sdk-libsparse-utils unzip python3)" >&2; exit 1; }
done
df -h "$WORK" | tail -1
free_gb=$(df -BG --output=avail "$WORK" | tail -1 | tr -dc '0-9')
[ "$free_gb" -ge 32 ] || { echo "error: need >=32 GB free under $WORK (have ${free_gb}G)" >&2; exit 1; }

echo "== extract BuildManifest + DMGs =="
cd "$WORK"
unzip -o -q "$IPSW" 'BuildManifest.plist' '*.dmg'

ROLES=$(python3 - "$WORK" <<'PY'
import plistlib, sys, os
work = sys.argv[1]
d = plistlib.load(open(os.path.join(work, 'BuildManifest.plist'), 'rb'))
ident = d['BuildIdentities'][0]['Manifest']
want = {'OS': 'os', 'Cryptex1,SystemOS': 'sysos', 'Cryptex1,AppOS': 'appos'}
out = {}
for key, var in want.items():
    path = ident[key]['Info']['Path']
    out[var] = os.path.join(work, path)
    print(var, path, file=sys.stderr)
print(out['os'], out['sysos'], out['appos'])
PY
)
read -r OS_DMG SYSOS_DMG APPOS_DMG <<<"$ROLES"
for f in "$OS_DMG" "$SYSOS_DMG" "$APPOS_DMG"; do
	[ -f "$f" ] || { echo "error: missing $f" >&2; exit 1; }
done
ls -l "$OS_DMG" "$SYSOS_DMG" "$APPOS_DMG"

echo "== build $SIZE HFS+ root =="
rm -f ios16-root.img
"$TREE/tools/mkiosroot.sh" "$OS_DMG" "$SYSOS_DMG" "$APPOS_DMG" "$WORK/ios16-root.img" "$SIZE"

echo "== fsck + bring-up tweaks =="
sudo fsck.hfsplus -fy "$WORK/ios16-root.img"
sudo mkdir -p /mnt/iosroot
sudo mount -t hfsplus -o loop,force "$WORK/ios16-root.img" /mnt/iosroot
sudo python3 "$TREE/tools/sweet-root-tweaks.py" /mnt/iosroot
sudo umount /mnt/iosroot

echo "== sparse image =="
img2simg "$WORK/ios16-root.img" "$WORK/ios16-root.simg"
sha256sum "$WORK/ios16-root.simg" | tee "$WORK/ios16-root.simg.sha256"
ls -l "$WORK/ios16-root.simg"
echo "done. flash with: fastboot -S 512M flash userdata $WORK/ios16-root.simg"
