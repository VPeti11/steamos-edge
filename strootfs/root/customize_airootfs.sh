#!/bin/bash
chmod +x /home/deck/Desktop/*
chmod +x /home/deck/tools/*
systemctl enable sddm
systemctl enable /etc/systemd/system/pr.service # Maybe this works
