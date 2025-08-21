#!/bin/bash
chmod +x /home/deck/Desktop/* || true
chmod +x /home/deck/tools/* || true
id -u deck &>/dev/null || useradd -M deck -g deck
chown -R deck /home/deck
echo -e "deck\ndeck" | passwd deck
echo -e "root\nroot" | passwd root
systemctl enable sddm
systemctl enable /etc/systemd/system/pr.service
mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/autologin.conf <<EOF
[Autologin]
User=deck
Session=plasma.desktop
EOF
getent group wheel >/dev/null || groupadd wheel
usermod -aG wheel deck
cp /etc/sudoers /etc/sudoers.bak
sed -i -e '/^%wheel ALL=(ALL) ALL/ s/^# *//' -e '/^%wheel ALL=(ALL) NOPASSWD: ALL/ d' /etc/sudoers
cat >> /etc/sudoers <<EOF
%wheel ALL=(ALL) NOPASSWD: ALL
EOF
sed -i 's/^#Server/Server/' /etc/pacman.d/mirrorlist
pacman-key --init
sed -i -E 's/^\s*SigLevel\s*=\s*Required\s+DatabaseOptional\s*/SigLevel = Never/' /etc/pacman.conf
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
ln -sf /usr/share/zoneinfo/UTC /etc/localtime
systemctl enable auto-sync-time.service
