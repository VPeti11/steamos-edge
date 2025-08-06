#!/bin/bash
chmod +x /home/deck/Desktop/*
chmod +x /home/deck/tools/*
systemctl enable sddm
useradd -M deck -g deck
chown -R deck /home/deck
echo -e "deck\ndeck" | sudo passwd deck
echo -e "root\nroot" | sudo passwd root
systemctl enable /etc/systemd/system/pr.service
sudo bash -c 'mkdir -p /etc/sddm.conf.d && echo -e "[Autologin]\nUser=deck\nSession=plasma.desktop" > /etc/sddm.conf.d/autologin.conf'
