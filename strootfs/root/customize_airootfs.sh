#!/bin/bash
chmod +x /home/deck/Desktop/*
chmod +x /home/deck/tools/*
systemctl enable sddm
useradd -M deck -g deck
chown -R deck /home/deck
echo -e "deck\ndeck" | sudo passwd deck
systemctl enable /etc/systemd/system/pr.service
sudo bash -c 'mkdir -p /etc/sddm.conf.d && echo -e "[Autologin]\nUser=deck\nSession=plasmax11.desktop" > /etc/sddm.conf.d/autologin.conf'
steamos-readonly disable
sudo grub-mkconfig -o /boot/grub/grub.cfg   

