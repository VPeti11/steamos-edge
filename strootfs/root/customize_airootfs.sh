#!/bin/bash
chmod +x /home/deck/Desktop/*
chmod +x /home/deck/tools/*
systemctl enable sddm
useradd -M deck -g deck
chown -R deck /home/deck
echo -e "deck\ndeck" | sudo passwd deck
systemctl enable /etc/systemd/system/pr.service
pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com
pacman-key --lsign-key 3056513887B78AEB
pacman -U 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst'
pacman -U 'https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst'
echo -e '\n[chaotic-aur]\nInclude = /etc/pacman.d/chaotic-mirrorlist' | sudo tee -a /etc/pacman.conf > /dev/null
pacman -S yay-bin
yay -S linux-firmware-valve heroic-games-launcher-bin opengamepadui-bin bottles --noconfirm --needed
steamos-readonly disable

