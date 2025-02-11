#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -e

if command -v pacman &> /dev/null
then
    echo "Pacman found"
else
    echo "Pacman not found"
    exit 1
fi

sudo chmod +x ./mksteamos
sudo ./mksteamos -v -w build/ -o build/ .
cd ./build/

file=$(ls SteamOS*.img 2>/dev/null)

if [[ -n $file ]]; then
    echo "Found file: $file"
    sudo dd if=./$file of=./steamos-edge.iso bs=4M status=progress
else
    echo "No matching file found."
fi