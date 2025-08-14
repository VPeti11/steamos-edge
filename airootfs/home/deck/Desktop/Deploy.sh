#!/bin/bash
set -euo pipefail

# --- helpers ---
norm_dev() {
  local d="$1"
  if [[ "$d" == /dev/* ]]; then
    echo "${d#/dev/}"
  else
    echo "${d}"
  fi
}

partpath() {
  local dev="$1"; local part="$2"
  if [[ "$dev" =~ ^(nvme|mmcblk|loop|rbd) ]] || [[ "$dev" =~ [0-9]$ ]]; then
    echo "/dev/${dev}p${part}"
  else
    echo "/dev/${dev}${part}"
  fi
}

ensure_bin() {
  for b in "$@"; do
    command -v "$b" >/dev/null 2>&1 || { echo "Missing required command: $b"; echo "Install dependencies and try again."; exit 1; }
  done
}

# required host tools
ensure_bin lsblk sgdisk parted mkfs.vfat mkfs.ext4 unsquashfs partprobe udevadm genfstab arch-chroot

echo "Available block devices:"
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT -e7
echo

# --- SOURCE ---
read -rp "Enter SOURCE device (e.g. sdb or /dev/sdb) where /arch/... is located: " SRC_DEV_RAW
SRC_DEV=$(norm_dev "$SRC_DEV_RAW")

read -rp "Enter SOURCE PARTITION NUMBER (e.g. 1) to mount (this partition must contain /arch): " SRC_PART_NUM
SRC_PART_PATH=$(partpath "$SRC_DEV" "$SRC_PART_NUM")

if [ ! -b "$SRC_PART_PATH" ]; then
  echo "Error: $SRC_PART_PATH not found. Aborting."
  exit 1
fi

mkdir -p /mnt/src_airoot
mount "$SRC_PART_PATH" /mnt/src_airoot
trap 'umount /mnt/src_airoot >/dev/null 2>&1 || true' EXIT

if [ ! -d /mnt/src_airoot/arch ]; then
  echo "No /arch directory found on $SRC_PART_PATH. Aborting."
  exit 1
fi

cd /mnt/src_airoot/arch

# find biggest folder (direct subfolders only)
BIGGEST_FOLDER=$(du -s --block-size=1 */ 2>/dev/null | sort -nr | head -n1 | awk '{print $2}' | sed 's:/$::')
if [ -z "$BIGGEST_FOLDER" ]; then
  echo "No subfolders found under /arch. Aborting."
  exit 1
fi

cd "$BIGGEST_FOLDER"
echo "Using folder: $PWD"

AIROOT_PATH="$PWD/airootfs.sfs"
if [ ! -f "$AIROOT_PATH" ]; then
  echo "airootfs.sfs not found in $PWD. Aborting."
  exit 1
fi

# --- DESTINATION ---
echo
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT -e7
echo
read -rp "Enter DESTINATION device to deploy to (e.g. sdc or /dev/sdc) : " DST_DEV_RAW
DST_DEV=$(norm_dev "$DST_DEV_RAW")
DST_DEV_NODE="/dev/${DST_DEV}"

if [ ! -b "$DST_DEV_NODE" ]; then
  echo "Error: $DST_DEV_NODE not found. Aborting."
  exit 1
fi

echo
echo "Choose target partitioning / boot mode:"
echo "  1) UEFI (GPT, 1 GiB ESP + root)"
echo "  2) BIOS (MBR/msdos, root)"
echo "  3) Both (GPT with BIOS-BOOT + 1 GiB ESP + root)"
read -rp "Select 1, 2 or 3: " PART_CHOICE

if [[ "$PART_CHOICE" != "1" && "$PART_CHOICE" != "2" && "$PART_CHOICE" != "3" ]]; then
  echo "Invalid selection. Aborting."
  exit 1
fi

echo "WARNING: All data on /dev/${DST_DEV} will be ERASED."
read -rp "Type EXACTLY 'ERASE /dev/${DST_DEV}' to confirm: " CONFIRM
if [ "$CONFIRM" != "ERASE /dev/${DST_DEV}" ]; then
  echo "Confirmation mismatch. Aborting."
  exit 0
fi

echo "Wiping partition table on ${DST_DEV_NODE}..."
sgdisk --zap-all "$DST_DEV_NODE"

# create partitions according to choice
if [[ "$PART_CHOICE" == "1" ]]; then
  parted -s "$DST_DEV_NODE" mklabel gpt
  parted -s "$DST_DEV_NODE" mkpart primary fat32 1MiB 1025MiB
  parted -s "$DST_DEV_NODE" set 1 esp on
  parted -s "$DST_DEV_NODE" mkpart primary ext4 1025MiB 100%
  DST_ESP=$(partpath "$DST_DEV" 1)
  DST_ROOT=$(partpath "$DST_DEV" 2)

elif [[ "$PART_CHOICE" == "2" ]]; then
  parted -s "$DST_DEV_NODE" mklabel msdos
  parted -s "$DST_DEV_NODE" mkpart primary ext4 1MiB 100%
  DST_ESP=""
  DST_ROOT=$(partpath "$DST_DEV" 1)

else
  parted -s "$DST_DEV_NODE" mklabel gpt
  parted -s "$DST_DEV_NODE" mkpart primary 1MiB 3MiB
  parted -s "$DST_DEV_NODE" set 1 bios_grub on
  parted -s "$DST_DEV_NODE" mkpart primary fat32 3MiB 1027MiB
  parted -s "$DST_DEV_NODE" set 2 esp on
  parted -s "$DST_DEV_NODE" mkpart primary ext4 1027MiB 100%
  DST_BIOS_GRUB=$(partpath "$DST_DEV" 1)
  DST_ESP=$(partpath "$DST_DEV" 2)
  DST_ROOT=$(partpath "$DST_DEV" 3)
fi

partprobe "$DST_DEV_NODE" || true
udevadm settle

for i in {1..10}; do
  if [[ -n "${DST_ROOT:-}" && -b "$DST_ROOT" ]]; then
    if [[ -n "${DST_ESP:-}" ]]; then
      [ -b "$DST_ESP" ] && break
    else
      break
    fi
  fi
  echo "Waiting for partitions to appear..."
  sleep 1
done

if [[ -n "${DST_ESP:-}" && -n "${DST_ROOT:-}" ]]; then
  if [ ! -b "$DST_ESP" ] || [ ! -b "$DST_ROOT" ]; then
    echo "Timed out waiting for partition devices. Aborting."
    exit 1
  fi
elif [[ -n "${DST_ROOT:-}" ]]; then
  if [ ! -b "$DST_ROOT" ]; then
    echo "Timed out waiting for root partition device. Aborting."
    exit 1
  fi
fi

# Format partitions
if [[ -n "${DST_ESP:-}" ]]; then
  echo "Formatting ESP ${DST_ESP} (FAT32)..."
  mkfs.vfat -F32 "$DST_ESP"
fi
echo "Formatting root ${DST_ROOT} (ext4)..."
mkfs.ext4 -F "$DST_ROOT"

# mount target partitions
mkdir -p /mnt/deploy_root
mount "$DST_ROOT" /mnt/deploy_root

if [[ -n "${DST_ESP:-}" ]]; then
  mkdir -p /mnt/deploy_root/boot
  mount "$DST_ESP" /mnt/deploy_root/boot
fi

# extract squashfs
echo "Extracting $AIROOT_PATH to /mnt/deploy_root ..."
unsquashfs -f -d /mnt/deploy_root "$AIROOT_PATH"

# --- find kernel/initrd in source (archiso-ish) ---
KERNEL_PATH=""
INITRD_PATH=""
while IFS= read -r -d '' k; do KERNEL_PATH="$k"; break; done < <(find "$PWD" -maxdepth 3 -type f \( -name 'vmlinuz*' -o -name 'vmlinux*' -o -name 'linux' \) -print0 2>/dev/null)
while IFS= read -r -d '' i; do INITRD_PATH="$i"; break; done < <(find "$PWD" -maxdepth 3 -type f \( -name 'initramfs*' -o -name 'initrd*' -o -name '*.img' \) -print0 2>/dev/null)

# fallback: entire source partition
if [ -z "$KERNEL_PATH" ]; then
  while IFS= read -r -d '' k; do KERNEL_PATH="$k"; break; done < <(find /mnt/src_airoot -type f \( -name 'vmlinuz*' -o -name 'vmlinux*' -o -name 'linux' \) -print0 2>/dev/null)
fi
if [ -z "$INITRD_PATH" ]; then
  while IFS= read -r -d '' i; do INITRD_PATH="$i"; break; done < <(find /mnt/src_airoot -type f \( -name 'initramfs*' -o -name 'initrd*' -o -name '*.img' \) -print0 2>/dev/null)
fi

KNAME=""; INAME=""
if [ -n "$KERNEL_PATH" ] && [ -n "$INITRD_PATH" ]; then
  echo "Found kernel: $KERNEL_PATH"
  echo "Found initrd: $INITRD_PATH"
  mkdir -p /mnt/deploy_root/boot
  cp -v "$KERNEL_PATH" "$INITRD_PATH" /mnt/deploy_root/boot/
  KNAME="$(basename "$KERNEL_PATH")"
  INAME="$(basename "$INITRD_PATH")"
  if [[ -n "${DST_ESP:-}" ]]; then
    cp -v "$KERNEL_PATH" "$INITRD_PATH" /mnt/deploy_root/boot/ || true
  fi
else
  echo "Kernel/initramfs not found automatically. Not installing linux package automatically to avoid initramfs generation."
fi

# get uuid for root
ROOT_UUID=$(blkid -s UUID -o value "$DST_ROOT" || true)

# --- genfstab + resolv.conf copy ---
echo "Generating fstab for the new system..."
genfstab -U /mnt/deploy_root > /mnt/deploy_root/etc/fstab

if [ -f /etc/resolv.conf ]; then
  cp -L /etc/resolv.conf /mnt/deploy_root/etc/resolv.conf
fi

# --- PACKAGES (NO 'linux', NO mkinitcpio) ---
# Install packages that do NOT trigger initramfs generation.
# NOTE: if you later want linux (kernel) installed, install it manually inside the installed system
# and run mkinitcpio there at your convenience.
PKGS=(
  grub
  linux-firmware
  efibootmgr
  os-prober
  networkmanager
  dbus
  xorg-server
  plasma
  plasma-x11-session
  qt5-wayland
)

echo "Installing packages into deployed root (excluding linux) ..."
arch-chroot /mnt/deploy_root /bin/bash -c "pacman -Sy --noconfirm ${PKGS[*]}" || {
  echo "Warning: pacman inside chroot failed. You may need to arch-chroot /mnt/deploy_root and run:"
  echo "  pacman -Sy --needed ${PKGS[*]}"
  # continue — user asked minimal chroot changes
}

arch-chroot /mnt/deploy_root /bin/bash -c "getent group wheel || groupadd wheel"
arch-chroot /mnt/deploy_root /bin/bash -c "usermod -aG wheel,storage,optical,audio,video,uucp,games,network,power,scanner,disk,sys,rfkill,lp deck"

arch-chroot /mnt/deploy_root /bin/bash -c "
systemctl enable dbus
systemctl enable NetworkManager
systemctl enable systemd-logind
"

AUTLOGIN_USER=$(awk -F: '($3>=1000)&&($1!="nobody"){print $1; exit}' /mnt/deploy_root/etc/passwd || true)
if [[ -n "$AUTLOGIN_USER" ]]; then
  echo "Configuring autologin for user: deck"

  GETTY_DIR="/mnt/deploy_root/etc/systemd/system/getty@tty1.service.d"
  mkdir -p "$GETTY_DIR"
  cat > "$GETTY_DIR/override.conf" <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin deck --noclear %I \$TERM
Type=idle
EOF

  USER_HOME=$(awk -F: -v u="$AUTLOGIN_USER" '($1==u){print $6; exit}' /mnt/deploy_root/etc/passwd)
  if [[ -n "$USER_HOME" ]]; then
    mkdir -p "/mnt/deploy_root${USER_HOME}"
    UIDN=$(awk -F: -v u="$AUTLOGIN_USER" '($1==u){print $3; exit}' /mnt/deploy_root/etc/passwd)
    GIDN=$(awk -F: -v u="$AUTLOGIN_USER" '($1==u){print $4; exit}' /mnt/deploy_root/etc/passwd)
    chown "$UIDN:$GIDN" "/mnt/deploy_root${USER_HOME}" || true

    BASH_PROFILE="/mnt/deploy_root${USER_HOME}/.bash_profile"
    MARKER="# <autostart-plasma-by-getty-autologin>"
    if [[ ! -f "$BASH_PROFILE" || -z "$(grep -F "$MARKER" "$BASH_PROFILE" 2>/dev/null || true)" ]]; then
      cat > "$BASH_PROFILE" <<'BPF'
# <autostart-plasma-by-getty-autologin>
# Start Plasma automatically on tty1 (autologin via getty).
# Prefer Wayland using plasma-dbus-run-session-if-needed; fall back to X11.
if [ -z "$DISPLAY" ] && [ "$(tty)" = /dev/tty1 ]; then
  # Preferred: Wayland using the plasma helper which sets up DBus session if needed
  if [ -x /usr/lib/plasma-dbus-run-session-if-needed ] && [ -x /usr/bin/startplasma-wayland ]; then
    exec /usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland
  # Fallback: classic X11 Plasma
  elif [ -x /usr/bin/startplasma-x11 ]; then
    if command -v dbus-run-session >/dev/null 2>&1; then
      exec dbus-run-session -- /usr/bin/startplasma-x11
    elif command -v dbus-launch >/dev/null 2>&1; then
      exec dbus-launch --exit-with-session /usr/bin/startplasma-x11
    else
      exec /usr/bin/startplasma-x11
    fi
  fi
fi
# end marker

BPF
      chown "$UIDN:$GIDN" "$BASH_PROFILE" || true
      chmod 0644 "$BASH_PROFILE"
      echo "Wrote $BASH_PROFILE"
    else
      echo "$BASH_PROFILE already contains autostart marker; leaving unchanged."
    fi
  fi
else
  echo "No regular user (UID>=1000) found in deployed root; skipping autologin files."
fi

# NOTE: we do NOT enable NetworkManager or other services here (user requested minimal chroot changes).

# --- BOOTLOADER: install only grub inside chroot and generate grub.cfg ---
echo "Installing GRUB bootloader (inside chroot) according to partitioning choice..."
if [[ "$PART_CHOICE" == "1" ]]; then
  arch-chroot /mnt/deploy_root /usr/bin/grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --recheck --no-nvram || \
    arch-chroot /mnt/deploy_root /usr/bin/grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --removable --recheck || \
    echo "grub-install (UEFI) may have failed; inspect chroot."
  arch-chroot /mnt/deploy_root /usr/bin/grub-mkconfig -o /boot/grub/grub.cfg || echo "grub-mkconfig failed."

elif [[ "$PART_CHOICE" == "2" ]]; then
  arch-chroot /mnt/deploy_root /usr/bin/grub-install --target=i386-pc --recheck "$DST_DEV_NODE" || echo "grub-install (BIOS) failed."
  arch-chroot /mnt/deploy_root /usr/bin/grub-mkconfig -o /boot/grub/grub.cfg || echo "grub-mkconfig failed."

else
  arch-chroot /mnt/deploy_root /usr/bin/grub-install --target=i386-pc --recheck "$DST_DEV_NODE" || echo "grub-install (BIOS) failed."
  arch-chroot /mnt/deploy_root /usr/bin/grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --recheck --no-nvram || \
    arch-chroot /mnt/deploy_root /usr/bin/grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB --removable --recheck || \
    echo "grub-install (UEFI) may have failed."
  arch-chroot /mnt/deploy_root /usr/bin/grub-mkconfig -o /boot/grub/grub.cfg || echo "grub-mkconfig failed."
fi

# final sync & cleanup
sync
umount /mnt/deploy_root/boot 2>/dev/null || true
umount /mnt/deploy_root 2>/dev/null || true
umount /mnt/src_airoot 2>/dev/null || true
trap - EXIT

echo "Done. Packages (excluding linux) installed; autologin files written; GRUB installed."
echo "IMPORTANT: If you want a working bootable kernel, you must either:"
echo "  - have copied kernel+initrd from the ISO into /boot (the script copies them if found), OR"
echo "  - install 'linux' in the installed system and run 'mkinitcpio -P' there."
echo
echo "To manually finish inside the installed system (after boot or via chroot):"
echo "  # arch-chroot /mnt/deploy_root"
echo "  pacman -S linux mkinitcpio   # if you need kernel & initramfs"
echo "  mkinitcpio -P"
echo "  systemctl enable NetworkManager"
echo "  exit"
