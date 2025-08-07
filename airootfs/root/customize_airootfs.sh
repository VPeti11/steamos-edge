#!/bin/bash
chmod +x /home/deck/Desktop/*
chmod +x /home/deck/tools/*
useradd -M deck -g deck
chown -R deck /home/deck
echo -e "deck\ndeck" | sudo passwd deck
echo -e "root\nroot" | sudo passwd root
systemctl enable /etc/systemd/system/pr.service
sudo bash -c 'mkdir -p /etc/sddm.conf.d && echo -e "[Autologin]\nUser=deck\nSession=plasma.desktop" > /etc/sddm.conf.d/autologin.conf'
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d/
sudo bash -c 'cat > /etc/systemd/system/getty@tty1.service.d/override.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin deck --noclear %I \$TERM
EOF'
sudo systemctl enable getty@tty1
sudo bash -c 'cat > /home/deck/.bash_profile <<EOF
if [[ -z \$WAYLAND_DISPLAY && \$XDG_VTNR -eq 1 ]]; then
  exec dbus-run-session startplasma-wayland
fi
EOF'

sudo chown deck:deck /home/deck/.bash_profile
